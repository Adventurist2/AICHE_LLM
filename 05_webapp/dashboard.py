"""AIChE trend explorer. Run: streamlit run 05_webapp/app.py"""
import json
import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from rapidfuzz import fuzz
from streamlit_searchbox import st_searchbox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from search import IndexBundle, search, INDEX_DIR, EMBEDDING_MODEL_NAME
from countries import COUNTRY_CODES, country_counts
from institutions import institute_summary, keyword_summary
from ui import apply_style, style_chart, ranking_chart, palette, search_style, CHART_CONFIG

@st.cache_resource(show_spinner='Loading search model...')
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


@st.cache_resource(show_spinner='Loading selected clustering...', max_entries=2)
def get_bundle(index_dir, version):
    return IndexBundle.load(index_dir, model=get_model())


@st.cache_resource(show_spinner=False)
def get_keyword_stats(path, version):
    return json.loads(Path(path).read_text(encoding='utf-8'))


@st.cache_resource(show_spinner='Loading institute affiliations...')
def get_institutions(directory, version):
    directory = Path(directory)
    metadata = json.loads((directory / 'institution_meta.json').read_text(encoding='utf-8'))
    return (metadata, pd.read_parquet(directory / 'institution_links.parquet'),
            pd.read_parquet(directory / 'institution_papers.parquet'),
            pd.read_parquet(directory / 'paper_keywords.parquet'))


def csv_bytes(frame):
    return frame.to_csv(index=False).encode('utf-8-sig')


@st.cache_data(show_spinner=False, max_entries=2)
def download_file(path, version):
    return Path(path).read_bytes()


def supporting_papers(selected_links, paper_table):
    grouped = selected_links.groupby('paper_id').agg(
        Keywords=('keyword', lambda s: ', '.join(sorted(set(s)))),
        **{'Institutes / affiliations': ('institute', lambda s: '; '.join(sorted(set(s)))),
           'Recorded affiliations': ('recorded_affiliations', lambda s: '\n'.join(sorted(set(s))))})
    table = grouped.reset_index().merge(paper_table, on='paper_id')
    return table.rename(columns={'title': 'Paper', 'year': 'Year', 'url': 'Paper link', 'source_file': 'Source file'})[
        ['Paper', 'Year', 'Keywords', 'Institutes / affiliations', 'Recorded affiliations', 'Paper link', 'Source file']]


def show_papers(selected_links, paper_table, key):
    table = supporting_papers(selected_links, paper_table)
    st.dataframe(table.drop(columns=['Source file']), hide_index=True, width='stretch',
                 column_config={'Paper link': st.column_config.LinkColumn('Paper link')})
    st.download_button('Download papers', csv_bytes(table),
                       file_name='institute_supporting_papers.csv', mime='text/csv', key=key, on_click='ignore')


def select_keyword(value):
    st.session_state['selected_keyword'] = value


def clear_keyword():
    st.session_state.pop('selected_keyword', None)


def choose_example(value):
    select_keyword(value)
    st.session_state['_search_revision'] = st.session_state.get('_search_revision', 0) + 1



def context():
    return st.session_state['_atlas_context']

def remember_scope():
    st.session_state['stats_scope'] = st.session_state['_scope_widget']

def remember_institute():
    st.session_state['institute_pick'] = st.session_state['_institute_pick']

def selected_context(ctx):
    bundle, data = ctx['bundle'], ctx['institution_data']
    anchor = st.session_state.get('selected_keyword')
    row = bundle.row_for_keyword(anchor) if anchor else None
    if row is None or data is None:
        return None
    keywords = [anchor] if st.session_state.get('stats_scope', 'Whole theme') == 'One keyword' else bundle.member_keywords(row)
    institute_meta, links, paper_table, paper_keywords = data
    selected_links = links[links.keyword.isin(keywords)]
    return dict(selected_links=selected_links, matched_papers=paper_keywords[paper_keywords.keyword.isin(keywords)].paper_id.nunique(), attributed_papers=selected_links.paper_id.nunique())

def render_explorer():
    ctx = context()
    bundle, stats, threshold, institution_data = (ctx[k] for k in ('bundle', 'stats', 'threshold', 'institution_data'))
    st.title('Research explorer')
    st.caption('Search a theme and inspect its research footprint.')
    search_column = st.container(border=True, key='explorer_controls')
    def suggestions(term):
        results = search(term, bundle, top_n=8)
        out = []
        for rec in results:
            members = bundle.member_keywords(rec['row_idx'])
            anchor = max(members, key=lambda kw: fuzz.ratio(term.casefold(), kw.casefold()))
            out.append((f"{rec['representative']} · {rec['total_count']:,} mentions · {rec['size']} keywords", anchor))
        return out


    if st.session_state.get('_search_threshold') != threshold:
        st.session_state['_search_threshold'] = threshold
        st.session_state['_search_revision'] = st.session_state.get('_search_revision', 0) + 1
    search_key = f"theme_search_{st.session_state['_search_revision']}"
    with search_column:
        st.markdown('Find a research theme')
        selection = st_searchbox(suggestions, placeholder='Search keywords, e.g. CO2 capture',
                                 key=search_key,
                                 default_searchterm=st.session_state.get('selected_keyword', ''),
                                 style_overrides=search_style(),
                                 submit_function=select_keyword, reset_function=clear_keyword)
    anchor = st.session_state.get('selected_keyword')
    row = bundle.row_for_keyword(anchor) if anchor else None
    st.divider()

    if row is not None:
        theme = bundle.cluster_row(row)
        members = bundle.member_keywords(row)
        st.subheader(theme['representative'])
        st.caption(f"Selected keyword · {anchor}")
        scope = st.radio('Show statistics for', ['Whole theme', 'One keyword'], horizontal=True, key='_scope_widget', index=['Whole theme', 'One keyword'].index(st.session_state.get('stats_scope', 'Whole theme')), on_change=remember_scope)
        rec = theme
        label = theme['representative']
        if scope == 'One keyword':
            keyword = st.selectbox('Keyword', sorted(members), index=sorted(members).index(anchor),
                                   key=f'member_{threshold:g}_{row}_{anchor}')
            rec = stats[keyword]
            label = keyword
            st.session_state['selected_keyword'] = keyword
        selected_keywords = [keyword] if scope == 'One keyword' else members
        counts = country_counts(rec.get('countries', {}))
        selected_links = None
        matched_papers = attributed_papers = 0
        if institution_data is not None:
            institute_meta, links, paper_table, paper_keywords = institution_data
            selected_links = links[links.keyword.isin(selected_keywords)]
            matched_papers = paper_keywords[paper_keywords.keyword.isin(selected_keywords)].paper_id.nunique()
            attributed_papers = selected_links.paper_id.nunique()
        with st.container(key='selection_metrics'):
            cols = st.columns(4 if institution_data is not None else 3)
        cols[0].metric('Keyword mentions' if scope == 'One keyword' else 'Theme keyword mentions', f"{rec['total_count']:,}")
        cols[1].metric('Keywords in theme', len(members))
        cols[2].metric('Mapped countries', sum(country in COUNTRY_CODES for country in counts))
        if institution_data is not None:
            cols[3].metric('Papers with affiliations', f'{attributed_papers:,}')
        st.caption('Mentions count occurrences, not unique papers. Keywords in theme measures cluster breadth; mapped countries measures geographic spread. Papers with affiliations measures source-backed coverage.')
        st.page_link('views/about.py', label='How to read these metrics →')
        left, right = st.columns(2)
        with left:
            with st.container(border=True, key='trend_chart'):
                st.subheader('Research over time')
                st.caption('Keyword mentions by meeting year')
                st.write('Higher points mean more occurrences in the processed records. Meeting size and extraction coverage also affect this count; it is not a normalized growth rate.')
                years = pd.DataFrame([(int(y), n) for y, n in rec.get('years', {}).items()], columns=['Year', 'Mentions']).sort_values('Year')
                if years.empty:
                    st.info('No year data.')
                else:
                    fig = style_chart(px.line(years, x='Year', y='Mentions', markers=True,
                                              color_discrete_sequence=[palette()['accent']]), height=330)
                    fig.update_traces(line_width=2.5, marker_size=7, fill='tozeroy',
                                      fillcolor='rgba(113,210,178,.08)' if st.session_state.get('dark_mode') else 'rgba(13,116,102,.07)',
                                      hovertemplate='%{x}<br>%{y:,} keyword mentions<extra></extra>')
                    fig.update_xaxes(tickmode='array', tickvals=years.Year.tolist(), tickformat='d')
                    st.plotly_chart(fig, width='stretch', config=CHART_CONFIG)
        with right:
            with st.container(border=True, key='geography_chart'):
                st.subheader('Around the world')
                st.caption('Keyword mentions by reported country')
                st.write('Darker countries have more mentions linked to their reported names. This shows observed activity, not research quality or the number of institutes.')
                countries = pd.DataFrame(sorted(counts.items(), key=lambda pair: -pair[1]), columns=['Country', 'Mentions'])
                countries['ISO3'] = countries['Country'].map(COUNTRY_CODES)
                mapped = countries.dropna(subset=['ISO3'])
                if not mapped.empty:
                    fig = style_chart(px.choropleth(mapped, locations='ISO3', locationmode='ISO-3', color='Mentions',
                                        hover_name='Country', hover_data={'ISO3': False, 'Mentions': True},
                                        color_continuous_scale=[palette()['faint'], palette()['accent']]), height=330)
                    fig.update_geos(projection_type='natural earth', showframe=False, showcoastlines=False,
                                    showland=True, landcolor=palette()['land'], bgcolor='rgba(0,0,0,0)')
                    fig.update_layout(coloraxis_colorbar=dict(title='Mentions', thickness=9, len=.65))
                    st.plotly_chart(fig, width='stretch', config=CHART_CONFIG)
                else:
                    st.info('No mappable country data.')
                with st.expander('Country counts'):
                    st.dataframe(countries[['Country', 'Mentions']], hide_index=True, width='stretch')
                    unmapped = countries[countries.ISO3.isna()]
                    if not unmapped.empty:
                        st.caption('Shown in the table only: ' + ', '.join(unmapped.Country))
        with st.expander(f'See all {len(members)} keywords in this theme'):
            st.write(', '.join(sorted(members)))
        st.page_link('views/institutes.py', label='See contributing institutes and supporting papers →')

    else:
        st.caption('Start with a keyword above, or browse the research landscape below.')
        with st.container(horizontal=True, gap='small'):
            for example in ('co2 capture', 'catalysis', 'machine learning'):
                if bundle.row_for_keyword(example) is not None:
                    st.button(example, key=f'example_{example}', on_click=choose_example, args=(example,))



def render_trends():
    ctx = context()
    bundle, stats, threshold, institution_data = (ctx[k] for k in ('bundle', 'stats', 'threshold', 'institution_data'))
    st.title('Research trends')
    st.caption('Which themes appear most often in a meeting year?')
    st.write('Bar length counts keyword mentions across a theme’s members. Use this ranking to explore prominent topics in the selected meeting; it does not measure scientific impact. Compare coverage before comparing years.')
    years = sorted(bundle.cluster_year['year'].unique(), reverse=True)
    if years:
        chosen_year = st.selectbox('Year', years, key='year_pick')
        n = st.slider('Show top N', 5, 30, 15, key='year_top_n')
        top = bundle.cluster_year[bundle.cluster_year.year == chosen_year].merge(
            bundle.clusters[['row_idx', 'representative']], on='row_idx').sort_values('count', ascending=False).head(n)
        fig = px.bar(top, x='count', y='representative', orientation='h')
        st.plotly_chart(ranking_chart(fig, len(top)), width='stretch', config=CHART_CONFIG)
        st.caption('Ranked by keyword mentions')
    st.page_link('views/about.py', label='Understanding trends and coverage →')


def render_geography():
    ctx = context()
    bundle, stats, threshold, institution_data = (ctx[k] for k in ('bundle', 'stats', 'threshold', 'institution_data'))
    st.title('Geographic landscape')
    st.caption('Explore prominent themes linked to a reported country.')
    st.write('Bar length counts keyword mentions attributed to this country. International records can credit several countries. These are reported names from extraction records, not independently geocoded author locations.')
    countries = sorted(bundle.cluster_country['country'].unique())
    if countries:
        chosen_country = st.selectbox('Country', countries,
                                     index=countries.index('United States') if 'United States' in countries else 0,
                                     key='country_pick')
        n = st.slider('Show top N', 5, 30, 15, key='country_top_n')
        top = bundle.cluster_country[bundle.cluster_country.country == chosen_country].groupby('row_idx', as_index=False)['count'].sum()
        top = top.merge(bundle.clusters[['row_idx', 'representative']], on='row_idx').sort_values('count', ascending=False).head(n)
        fig = px.bar(top, x='count', y='representative', orientation='h')
        st.plotly_chart(ranking_chart(fig, len(top)), width='stretch', config=CHART_CONFIG)
        st.caption('Ranked by keyword mentions')

    st.page_link('views/about.py', label='Understanding country counts →')


def render_institutes():
    ctx = context()
    bundle, stats, threshold, institution_data = (ctx[k] for k in ('bundle', 'stats', 'threshold', 'institution_data'))
    st.title('Institutes & papers')
    st.caption('Follow a theme to its affiliations, or browse an institute’s research.')
    mode = st.radio('Institute view', ['Selected theme', 'Browse institutes'], horizontal=True, key='institute_view')
    if mode == 'Browse institutes':
        st.write('Keyword and theme rows count distinct supporting papers; a paper can contribute to several rows. '
                 'Use these tables to inspect research participation and topics, not institutional quality. '
                 'The Years column lists meetings represented by the supporting papers.')
        if institution_data is None:
            st.info('Prepare institute data with: python 05_webapp/institutions.py')
        else:
            institute_meta, links, paper_table, paper_keywords = institution_data
            st.caption(f"Browse {institute_meta['institutes']:,} recorded institute / affiliation names "
                       f"from {institute_meta['papers_with_affiliations']:,} papers.")
            names = sorted(links.institute.unique())
            if names:
                institute = st.selectbox('Find an institute', names,
                                        index=names.index(st.session_state['institute_pick']) if st.session_state.get('institute_pick') in names else (names.index('Massachusetts Institute of Technology') if 'Massachusetts Institute of Technology' in names else 0), key='_institute_pick', on_change=remember_institute)
                table = keyword_summary(links, institute)
                st.dataframe(table, hide_index=True, width='stretch')
                st.download_button('Download keywords', csv_bytes(table),
                                   file_name='institute_keywords.csv', mime='text/csv', key='institute_keywords_csv', on_click='ignore')
                institute_links = links[links.institute == institute]
                # Theme membership follows the current height; keyword counts stay paper-based.
                themed = institute_links[['paper_id', 'keyword']].drop_duplicates().copy()
                themed['row_idx'] = themed.keyword.map(bundle.row_for_keyword)
                themed = themed.dropna(subset=['row_idx'])
                themes = themed.groupby('row_idx').agg(Papers=('paper_id', 'nunique'), Keywords=('keyword', 'nunique'))
                themes = themes.reset_index().merge(bundle.clusters[['row_idx', 'representative']], on='row_idx')
                themes = themes.rename(columns={'representative': 'Theme'}).sort_values('Papers', ascending=False)
                st.subheader(f'Research themes at threshold {threshold:.2f}')
                st.dataframe(themes[['Theme', 'Papers', 'Keywords']], hide_index=True, width='stretch')
                with st.expander('Supporting papers for this institute'):
                    show_papers(institute_links, paper_table, 'institute_papers_csv')
            full_csv = Path(INDEX_DIR) / 'institute_keywords.csv'
            if full_csv.exists():
                st.download_button('Download all institute–keyword pairs', download_file(str(full_csv), full_csv.stat().st_mtime_ns),
                                   file_name='all_institute_keywords.csv', mime='text/csv', key='all_institute_keywords_csv', on_click='ignore')
            with st.expander('Affiliation coverage by year'):
                coverage = pd.DataFrame.from_dict(institute_meta['coverage_by_year'], orient='index').fillna(0).astype(int)
                st.dataframe(coverage.rename_axis('Year').reset_index(), hide_index=True, width='stretch')
                st.caption('Coverage counts source-file/title references before duplicate papers are combined. '
                           'Missing or ambiguous source/title matches are excluded, and missing affiliations are not inferred.')
        return
    if institution_data is None:
        st.info('Institute affiliations are not available for this snapshot.')
        return
    selection = selected_context(ctx)
    if selection is None:
        st.info('Select a keyword on the Explorer page to see its contributing institutes.')
        st.page_link('views/explorer.py', label='Open Explorer →')
        return
    institute_meta, links, paper_table, paper_keywords = institution_data
    selected_links, matched_papers, attributed_papers = (selection[k] for k in ('selected_links', 'matched_papers', 'attributed_papers'))
    st.caption(f"Selected keyword · {st.session_state['selected_keyword']} · {st.session_state.get('stats_scope', 'Whole theme')} · Height {threshold:.2f}")
    st.write('Papers counts unique source papers per institute; Keywords counts distinct linked terms. In Whole theme, an institute can contribute through a related keyword. These counts measure participation, not institutional quality.')
    st.subheader('Contributing institutes')
    if institution_data is None:
        st.info('Prepare the institute list with: python 05_webapp/institutions.py')
    else:
        institute_meta, links, paper_table, paper_keywords = institution_data
        st.caption(f'{attributed_papers:,} of {matched_papers:,} matched papers have recorded affiliations. '
                   'Each paper counts once per institute.')
        table = institute_summary(selected_links)
        if table.empty:
            st.info('No recorded institute affiliation could be linked to this selection.')
        else:
            st.dataframe(table, hide_index=True, width='stretch')
            st.download_button('Download institute list', csv_bytes(table),
                               file_name='keyword_institutes.csv', mime='text/csv', key='selected_institutes_csv', on_click='ignore')
            with st.expander('Supporting papers and affiliations'):
                show_papers(selected_links, paper_table, 'selected_papers_csv')

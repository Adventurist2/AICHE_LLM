"""Interactive top-theme and change rankings, derived from source-backed papers."""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from trend_analysis import load_paper_trends, rank_changes, rank_themes
from ui import palette, style_chart, CHART_CONFIG

DIRECTION_CHOICES = {
    'Both signs (largest magnitude)': 'Largest changes',
    'Positive trends (+)': 'Rising themes',
    'Negative trends (−)': 'Falling themes',
}


@st.cache_data(show_spinner='Counting distinct supporting papers…', max_entries=2)
def get_paper_trends(directory, versions, signature):
    return load_paper_trends(directory, signature)


def render_paper_trends(ctx, index_root):
    st.title('Top themes & trends')
    st.caption('Explore prominent themes in one year, or the largest increases and decreases between two years.')
    st.write('These rankings count distinct source-matched, keyword-bearing papers. A paper containing several member keywords counts once within a theme; it can support several themes.')
    if ctx['institution_data'] is None:
        st.info('Source-backed paper records are unavailable for this snapshot. Prepare matching paper indices to use these rankings.')
        return
    directory = Path(index_root) / f"dt{ctx['threshold']:g}"
    paths = [directory / name for name in ('meta.json', 'members.json', 'clusters.parquet')]
    paths += [Path(index_root) / name for name in ('institution_meta.json', 'paper_keywords.parquet', 'institution_papers.parquet')]
    try:
        versions = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
        data = get_paper_trends(str(directory), versions, ctx['meta']['aggregate_sha256'])
    except (OSError, ValueError, KeyError) as exc:
        st.error(f'Paper rankings could not be verified: {exc}')
        return
    years = [int(y) for y in data.denominators.index]
    modes = ['Rising & falling themes', 'Top themes in a year'] if len(years) > 1 else ['Top themes in a year']
    mode = st.radio('Ranking view', modes, horizontal=True, key='trend_view')
    changes = mode == 'Rising & falling themes'
    first, second, third = st.columns(3)
    if changes:
        start = first.selectbox('Start year', years[:-1], key='trend_start')
        endings = [y for y in years if y > start]
        if st.session_state.get('trend_end') not in endings:
            st.session_state['trend_end'] = endings[-1]
        end = second.selectbox('End year', endings, key='trend_end')
        legacy_direction = st.session_state.get('trend_direction')
        previous_labels = {value: label for label, value in DIRECTION_CHOICES.items()}
        if legacy_direction in previous_labels:
            st.session_state['trend_direction'] = previous_labels[legacy_direction]
        direction_label = third.selectbox('Trend direction', list(DIRECTION_CHOICES), key='trend_direction',
            help='Positive: largest increases. Negative: largest decreases. Both: largest absolute changes, keeping their signs; −5 pp ranks ahead of +3 pp.')
        direction = DIRECTION_CHOICES[direction_label]
        chosen_years = [start, end]
    else:
        year = first.selectbox('Meeting year', years, index=len(years)-1, key='trend_year')
        chosen_years = [year]
    count_col, support_col = st.columns([2, 1])
    requested = count_col.selectbox('Show top', [10, 20, 50, 100, 'Custom', 'All'], key='trend_count')
    if requested == 'Custom':
        if st.session_state.get('trend_custom', 1) > len(data.clusters):
            st.session_state['trend_custom'] = len(data.clusters)
        requested = count_col.number_input('Number of themes', min_value=1, max_value=max(1, len(data.clusters)),
            value=min(10, len(data.clusters)), key='trend_custom')
    minimum = support_col.number_input('Minimum supporting papers', min_value=1, value=1, key='trend_minimum',
        help='Distinct papers in the selected year, or the sum across the two comparison years.')
    result = rank_changes(data, start, end, direction, minimum) if changes else rank_themes(data, year, minimum)
    shown = result if requested == 'All' else result.head(int(requested))
    st.caption(f"Height {ctx['threshold']:.2f} · showing {len(shown):,} of {len(result):,} qualifying themes · " +
        ' / '.join(f'{y}: {data.denominators[y]:,} eligible papers' for y in chosen_years))
    partial = set((ctx.get('coverage_data') or {}).get('partial_years', []))
    if partial.intersection(chosen_years):
        st.warning('This comparison includes an explicitly partial extraction year. Treat changes as exploratory.')
    st.caption('Coverage varies across all years. Normalization adjusts observed paper volume, not missing-data bias. Automatic theme labels need review.')
    if shown.empty:
        st.info('No themes meet these filters. Lower the minimum support or change direction/years.')
        return
    if changes:
        st.write('Change = end-year paper share − start-year paper share, in percentage points. Positive shows increases; Negative shows decreases. Both ranks by absolute magnitude while keeping the sign: −5 pp comes before +3 pp. It does not reserve equal slots for each sign. This is endpoint change, not a forecast.')
        columns = ['rank', 'representative', 'size', 'start_papers', 'end_papers', 'start_share_pct', 'end_share_pct', 'change_pp']
        names = ['Rank', 'Theme', 'Member keywords', f'{start} papers', f'{end} papers', f'{start} share (%)', f'{end} share (%)', 'Change (pp)']
    else:
        st.write('Themes are ranked by distinct paper count in this year. Paper share is that count divided by the eligible observed papers; shares can overlap across themes.')
        columns = ['rank', 'representative', 'size', 'papers', 'share_pct']
        names = ['Rank', 'Theme', 'Member keywords', 'Papers', 'Paper share (%)']
    table = shown[columns].copy()
    table.columns = names
    chart_tab, table_tab, evidence_tab = st.tabs(['Chart', 'Table & download', 'Evidence'])
    with chart_tab:
        plotted = shown.head(20).copy()
        plotted['label'] = plotted['rank'].astype(str) + '. ' + plotted.representative
        x = 'change_pp' if changes else 'share_pct'
        plotted['direction'] = ['Increase' if v > 0 else 'Decrease' if v < 0 else 'Unchanged' for v in plotted[x]]
        fig = px.bar(plotted, x=x, y='label', orientation='h', color='direction' if changes else None,
            color_discrete_map={'Increase': palette()['accent'], 'Decrease': '#C76B55', 'Unchanged': palette()['muted']},
            color_discrete_sequence=[palette()['accent']], hover_data=columns)
        style_chart(fig, height=max(300, len(plotted) * 25 + 70))
        fig.update_yaxes(autorange='reversed', showgrid=False,
                         categoryorder='array', categoryarray=plotted.label.tolist())
        fig.update_xaxes(title='Change (percentage points)' if changes else 'Observed paper share (%)', showgrid=True, gridcolor=palette()['grid'])
        st.plotly_chart(fig, width='stretch', config=CHART_CONFIG)
        if len(shown) > 20:
            st.caption('The chart shows the first 20 for readability. The table and CSV contain every requested qualifying result.')
    with table_tab:
        st.dataframe(table, hide_index=True, width='stretch', height=min(480, 38 + 35 * len(table)),
            column_config={name: st.column_config.NumberColumn(name, format='%.2f') for name in names if '%' in name or '(pp)' in name})
        st.download_button('Download displayed ranking', table.to_csv(index=False).encode('utf-8-sig'),
            file_name=f"theme_{'changes' if changes else 'ranking'}_dt{ctx['threshold']:g}.csv", mime='text/csv', key='trend_download', on_click='ignore')
    with evidence_tab:
        if st.session_state.get('trend_inspect_rank', 1) > len(shown):
            st.session_state['trend_inspect_rank'] = 1
        rank = st.number_input('Inspect result rank', min_value=1, max_value=len(shown), value=1, key='trend_inspect_rank')
        selected = shown.iloc[rank-1]
        row = int(selected.row_idx)
        st.markdown(f"**{selected.representative}**")
        with st.expander('Member keywords'):
            st.dataframe(pd.DataFrame({'Keyword': data.members[str(row)]}), hide_index=True, width='stretch', height=220)
        history = data.counts[data.counts.row_idx.eq(row)].set_index('year')
        observed = history.reindex(data.denominators.index).fillna({'papers': 0, 'share_pct': 0})
        history_frame = observed[['share_pct']].reindex(range(min(years), max(years)+1)).rename_axis('Year').reset_index()
        fig = px.line(history_frame, x='Year', y='share_pct', markers=True)
        style_chart(fig, height=280)
        fig.update_traces(connectgaps=False, line_color=palette()['accent'])
        fig.update_yaxes(title='Observed paper share (%)', rangemode='tozero')
        st.plotly_chart(fig, width='stretch', config=CHART_CONFIG)
        st.caption('Missing years break the line. All observed years are shown, including partial years; endpoint selection does not imply a steady trend.')
        ids = data.pairs.loc[data.pairs.row_idx.eq(row) & data.pairs.year.isin(chosen_years), 'paper_id']
        supporting = data.papers[data.papers.paper_id.isin(ids)].sort_values(['year', 'title', 'paper_id'])
        st.caption(f'{len(supporting):,} distinct source papers in the selected year(s). First 100 shown.')
        st.dataframe(supporting[['year', 'title', 'url']].head(100), hide_index=True, width='stretch', height=300,
            column_config={'url': st.column_config.LinkColumn('Paper link')})
        st.download_button('Download supporting papers', supporting.to_csv(index=False).encode('utf-8-sig'),
            file_name='theme_supporting_papers.csv', mime='text/csv', key='trend_papers_download', on_click='ignore')
    with st.expander('Counting method & coverage'):
        st.write('The denominator includes distinct source-matched papers with extracted keywords, including papers without affiliations. Unknown source matches and failed extractions are excluded. These are conditional observed-paper shares, not a census of research or a measure of impact. A move from 1% to 2% is +1 percentage point. No statistical significance is claimed.')
        st.dataframe(data.denominators.rename('Eligible papers').rename_axis('Year').reset_index(), hide_index=True, width='stretch')
    st.page_link('views/about.py', label='More about metrics and limitations →')

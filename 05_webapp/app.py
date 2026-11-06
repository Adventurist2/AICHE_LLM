"""AIChE Atlas multipage entrypoint."""
import os
import sys
import json
from pathlib import Path
import streamlit as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dashboard import get_bundle, get_keyword_stats, get_institutions, INDEX_DIR, apply_style
st.set_page_config(page_title='AIChE · Research Atlas', page_icon='🔬', layout='wide')
if 'dark_mode' not in st.session_state:
    st.session_state['dark_mode'] = st.query_params.get('theme', 'light') == 'dark'
apply_style()
def persist_appearance():
    st.query_params['theme'] = 'dark' if st.session_state['dark_mode'] else 'light'
if st.session_state['dark_mode']:
    st.query_params['theme'] = 'dark'
with st.container(key='page_header'):
    brand_column, appearance_column = st.columns([4, 1])
    with brand_column:
        st.markdown('<div class="brand"><span class="brand-mark">A</span> AIChE RESEARCH ATLAS</div>', unsafe_allow_html=True)
    with appearance_column:
        st.toggle('Dark mode', key='dark_mode', on_change=persist_appearance,
                  help='Switch between light and dark. Your choice is kept when you refresh this page.')

page = st.navigation([
    st.Page('views/explorer.py', title='Explorer', default=True),
    st.Page('views/trends.py', title='Trends', url_path='trends'),
    st.Page('views/geography.py', title='Geography', url_path='geography'),
    st.Page('views/institutes.py', title='Institutes', url_path='institutes'),
    st.Page('views/about.py', title='About & metrics', url_path='about'),
], position='top')
overview = st.empty()
coverage_notice = st.empty()
indices = {}
for path in Path(INDEX_DIR).glob('dt*/meta.json'):
    meta = json.loads(path.read_text(encoding='utf-8'))
    indices[float(meta['threshold'])] = (path.parent, meta, path.stat().st_mtime_ns)
if not indices:
    if page.title == 'About & metrics':
        from about import render_about
        render_about(None)
        st.stop()
    st.info('Prepare the threshold data before opening the explorer. See 05_webapp/README.md.')
    st.stop()

thresholds = sorted(indices)
with st.container(key='global_threshold'):
    with st.expander('Clustering controls · specific to broad', expanded=page.title == 'Explorer'):
        threshold = st.select_slider('Clustering distance threshold', options=thresholds,
                                     value=1.0 if 1.0 in indices else thresholds[0],
                                     format_func=lambda value: f'{value:.2f}', key='threshold')
        st.caption('Specific ← → Broad themes')
index_dir, meta, version = indices[threshold]
stats_path = Path(INDEX_DIR) / 'keyword_stats.json'
if not stats_path.exists():
    st.error('Keyword statistics are missing. Run 05_webapp/prepare_indices.py.')
    st.stop()
snapshot = get_keyword_stats(str(stats_path), stats_path.stat().st_mtime_ns)
if meta.get('aggregate_sha256') != snapshot.get('aggregate_sha256'):
    st.error('This threshold and the keyword statistics belong to different data snapshots. Rebuild the indices.')
    st.stop()
bundle = get_bundle(str(index_dir), version)
stats = snapshot['keywords']
coverage_data = None
coverage_path = Path(INDEX_DIR) / 'data_coverage.json'
if coverage_path.exists():
    try:
        loaded_coverage = get_keyword_stats(str(coverage_path), coverage_path.stat().st_mtime_ns)
        if loaded_coverage.get('aggregate_sha256') == snapshot.get('aggregate_sha256'):
            coverage_data = loaded_coverage
            partial = ', '.join(map(str, coverage_data.get('partial_years', [])))
            message = f"Data snapshot · {coverage_data['snapshot_date']}"
            if partial:
                message += f' · Partial extraction: {partial}. Trends reflect the processed records.'
            coverage_notice.caption(message)
    except (OSError, ValueError, KeyError):
        pass
institution_data = None
institution_path = Path(INDEX_DIR) / 'institution_meta.json'
if institution_path.exists():
    try:
        loaded = get_institutions(str(INDEX_DIR), institution_path.stat().st_mtime_ns)
        if loaded[0].get('aggregate_sha256') == snapshot.get('aggregate_sha256'):
            institution_data = loaded
        else:
            st.warning('Institute data needs refreshing. Run 05_webapp/institutions.py to match the current keywords.')
    except (OSError, ValueError):
        st.warning('Institute data is incomplete. Run 05_webapp/institutions.py to restore it.')
overview.markdown(f'<div class="overview"><span><strong>{meta["num_keywords"]:,}</strong> keywords</span>'
                  f'<span><strong>{len(bundle.clusters):,}</strong> themes</span>'
                  f'<span><strong>{len(bundle.cluster_year.year.unique())}</strong> meeting years</span>'
                  f'<span><strong>{int(bundle.clusters.total_count.sum()):,}</strong> mentions</span></div>',
                  unsafe_allow_html=True)


st.session_state['_atlas_context'] = dict(bundle=bundle, stats=stats, threshold=threshold,
    institution_data=institution_data, coverage_data=coverage_data, meta=meta, thresholds=thresholds)
page.run()
st.markdown('<div class="quiet-footer">AIChE Research Atlas · Themes, conference records and recorded affiliations</div>', unsafe_allow_html=True)

"""Exercise the Streamlit slider and map table against prepared source counts."""
import json
import base64
from pathlib import Path
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest
from countries import country_counts, COUNTRY_CODES
from search import IndexBundle, INDEX_DIR


def assert_map_counts(app, countries):
    mapped = {COUNTRY_CODES[name]: count for name, count in countries.items() if name in COUNTRY_CODES}
    if not mapped:
        return
    spec = json.loads(app.get('plotly_chart')[1].proto.spec)
    trace = spec['data'][0]
    values = trace['z']
    if isinstance(values, dict):
        values = np.frombuffer(base64.b64decode(values['bdata']), dtype=values['dtype']).tolist()
    assert trace['locationmode'] == 'ISO-3'
    assert dict(zip(trace['locations'], values)) == mapped


def verify():
    app = AppTest.from_file(str(Path(__file__).with_name('app.py')), default_timeout=60)
    snapshot = json.loads(Path(INDEX_DIR, 'keyword_stats.json').read_text(encoding='utf-8'))
    keyword = 'co2 capture'
    if keyword not in snapshot['keywords']:
        keyword = next(iter(snapshot['keywords']))
    app.session_state['selected_keyword'] = keyword
    app.run()
    assert not app.exception, app.exception
    assert app.select_slider[0].value == 1.0
    links = pd.read_parquet(Path(INDEX_DIR, 'institution_links.parquet'))
    def assert_institutes(keywords):
        app.switch_page('views/institutes.py').run()
        assert not app.exception, app.exception
        selected = links[links.keyword.isin(keywords)]
        expected = selected.groupby('institute').paper_id.nunique().to_dict()
        tables = [item.value for item in app.dataframe
                  if item.value.columns.tolist() == ['Institute / affiliation', 'Papers', 'Keywords', 'Keyword list']]
        actual = dict(zip(tables[0]['Institute / affiliation'], tables[0].Papers)) if tables else {}
        assert actual == expected, 'Institute list does not match selected keyword members'
        app.switch_page('views/explorer.py').run()
        assert not app.exception, app.exception
    heights = sorted(float(json.loads(path.read_text(encoding='utf-8'))['threshold'])
                     for path in Path(INDEX_DIR).glob('dt*/meta.json'))
    assert heights, 'No prepared heights'
    for height in heights:
        app.select_slider[0].set_value(height).run()
        assert not app.exception, app.exception
        assert app.session_state['selected_keyword'] == keyword
        bundle = IndexBundle.load(str(Path(INDEX_DIR, f'dt{height:g}')), model=object())
        rec = bundle.cluster_row(bundle.row_for_keyword(keyword))
        assert int(app.metric[0].value.replace(',', '')) == rec['total_count']
        table = app.dataframe[0].value
        assert dict(zip(table.Country, table.Mentions)) == rec['countries']
        assert_map_counts(app, rec['countries'])
        assert_institutes(bundle.member_keywords(rec['row_idx']))
        print(f'UI height {height:.2f}: selected keyword preserved; metrics, map and institute list match theme')
    app.radio[0].set_value('One keyword').run()
    assert not app.exception, app.exception
    rec = snapshot['keywords'][keyword]
    assert int(app.metric[0].value.replace(',', '')) == rec['total_count']
    table = app.dataframe[0].value
    assert dict(zip(table.Country, table.Mentions)) == country_counts(rec['countries'])
    assert_map_counts(app, country_counts(rec['countries']))
    assert_institutes([keyword])
    app.select_slider[0].set_value(0.75).run()
    assert not app.exception, app.exception
    assert app.session_state['selected_keyword'] == keyword
    table = app.dataframe[0].value
    assert dict(zip(table.Country, table.Mentions)) == country_counts(rec['countries'])
    assert_map_counts(app, country_counts(rec['countries']))
    assert_institutes([keyword])
    print('UI exact-keyword mode: metrics, map and institute list match source and persist after changing height')


if __name__ == '__main__':
    verify()

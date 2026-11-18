import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TrendPageTests(unittest.TestCase):
    def test_adjustable_count_direction_years_and_coarser_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pk = [(f'old{i}', 2014, f'kw{i}') for i in range(25)]
            pk += [(f'new{i}', 2024, f'kw{i}') for i in range(20)]
            pk += [('new0', 2024, 'kw1')]  # two terms from one merged theme must count once
            pd.DataFrame(pk, columns=['paper_id', 'year', 'keyword']).to_parquet(root / 'paper_keywords.parquet')
            papers = sorted(set((pid, year) for pid, year, _ in pk))
            pd.DataFrame([(pid, y, pid, f'https://example.test/{pid}', 'raw.json') for pid, y in papers],
                columns=['paper_id', 'year', 'title', 'url', 'source_file']).to_parquet(root / 'institution_papers.parquet')
            (root / 'institution_meta.json').write_text(json.dumps({'aggregate_sha256': 'fixture'}))
            for h, step in [(0.75, 1), (1.25, 2)]:
                target = root / f'dt{h:g}'
                target.mkdir()
                groups = [list(range(i, min(i+step, 25))) for i in range(0, 25, step)]
                pd.DataFrame([(i, f'cluster_{i+1}', f'Theme {i}', len(group)) for i, group in enumerate(groups)],
                    columns=['row_idx', 'cluster_id', 'representative', 'size']).to_parquet(target / 'clusters.parquet')
                (target / 'members.json').write_text(json.dumps({str(i): [f'kw{k}' for k in group] for i, group in enumerate(groups)}))
                (target / 'meta.json').write_text(json.dumps({'aggregate_sha256': 'fixture', 'threshold': h}))
            source = """
import streamlit as st
from trend_page import render_paper_trends
from unittest.mock import patch
st.set_page_config(layout='wide')
st.toggle('Dark mode', key='dark_mode')
height = st.select_slider('Height', options=[0.75, 1.25])
with patch('streamlit.page_link'):
    render_paper_trends(dict(threshold=height, institution_data=True,
        meta={'aggregate_sha256': 'fixture'}, coverage_data={'partial_years': []}), ROOT)
""".replace('ROOT', repr(str(root)))
            st.cache_data.clear()
            app = AppTest.from_string(source, default_timeout=30).run()
            def table():
                self.assertFalse(app.exception, str(app.exception))
                return next(frame.value for frame in app.dataframe if 'Theme' in frame.value.columns)
            self.assertEqual(len(table()), 10)
            chart = json.loads(app.get('plotly_chart')[0].proto.spec)
            self.assertEqual([int(label.split('.')[0]) for label in chart['layout']['yaxis']['categoryarray']], list(range(1, 11)))
            app.selectbox(key='trend_count').set_value(20).run()
            self.assertEqual(len(table()), 20)
            app.selectbox(key='trend_count').set_value('All').run()
            self.assertEqual(len(table()), 25)
            app.selectbox(key='trend_count').set_value('Custom').run()
            app.number_input(key='trend_custom').set_value(3).run()
            self.assertEqual(len(table()), 3)
            app.selectbox(key='trend_direction').set_value('Negative trends (−)').run()
            self.assertTrue(table()['Change (pp)'].lt(0).all())
            app.selectbox(key='trend_direction').set_value('Positive trends (+)').run()
            self.assertTrue(table()['Change (pp)'].gt(0).all())
            app.selectbox(key='trend_direction').set_value('Both signs (largest magnitude)').run()
            values = table()['Change (pp)']
            self.assertTrue(values.abs().is_monotonic_decreasing)
            self.assertTrue(values.gt(0).any() and values.lt(0).any())
            app.toggle(key='dark_mode').set_value(True).run()
            self.assertFalse(app.exception, str(app.exception))
            app.radio(key='trend_view').set_value('Top themes in a year').run()
            self.assertTrue('Papers' in table())
            app.selectbox(key='trend_count').set_value('All').run()
            self.assertEqual(len(table()), 20)
            app.selectbox(key='trend_year').set_value(2014).run()
            self.assertEqual(len(table()), 25)
            app.select_slider[0].set_value(1.25).run()
            self.assertEqual(len(table()), 13)
            app.radio(key='trend_view').set_value('Rising & falling themes').run()
            self.assertFalse(app.exception, str(app.exception))
            app.number_input(key='trend_minimum').set_value(999).run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertTrue(any('No themes meet' in item.value for item in app.info))
            st.cache_data.clear()


if __name__ == '__main__':
    unittest.main()

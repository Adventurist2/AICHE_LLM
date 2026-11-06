"""UI regression: merging themes must not leak countries into exact-keyword mode."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import search
from build_index import build
from verify_app import assert_map_counts


class ThresholdUITests(unittest.TestCase):
    def test_slider_keeps_keyword_and_map_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = {
                'capture': dict(total_count=40, years={'2023': 40}, countries={'United States': 33, 'USA': 7}),
                'storage': dict(total_count=20, years={'2023': 20}, countries={'Canada': 20}),
            }
            for height, groups in [(0.75, [['capture'], ['storage']]), (1.25, [['capture', 'storage']])]:
                clusters = {}
                for i, members in enumerate(groups):
                    countries = {}
                    for keyword in members:
                        for country, count in raw[keyword]['countries'].items():
                            countries[country] = countries.get(country, 0) + count
                    total = sum(raw[keyword]['total_count'] for keyword in members)
                    clusters[f'cluster_{i+1}'] = dict(representative=members[0], member_keywords=members,
                        total_count=total, years={'2023': total}, countries=countries, size=len(members))
                source = root / f'clusters{height}.json'
                source.write_text(json.dumps({'meta': {'num_keywords': 2, 'aggregate_sha256': 'fixture'},
                                             'clusters': clusters}), encoding='utf-8')
                with patch('build_index.load_leaf_embeddings', return_value=(
                    {'capture': 0, 'storage': 1}, np.array([[1., 0.], [0., 1.]]))):
                    build(height, str(source), str(root / f'dt{height:g}'))
            (root / 'keyword_stats.json').write_text(json.dumps(
                {'aggregate_sha256': 'fixture', 'keywords': raw}), encoding='utf-8')
            (root / 'data_coverage.json').write_text(json.dumps(dict(
                aggregate_sha256='fixture', snapshot_date='2026-10-13', partial_years=[2023],
                extraction_records_by_year={'2023': {'files': 1, 'records': 4, 'with_keywords': 3}})), encoding='utf-8')
            links = pd.DataFrame([
                ('p1', 2023, 'capture', 'Alpha University', 'Alpha University'),
                ('p2', 2023, 'storage', 'Beta University', 'Beta University'),
                ('p3', 2023, 'capture', 'Alpha University', 'Alpha University'),
                ('p3', 2023, 'storage', 'Alpha University', 'Alpha University'),
            ], columns=['paper_id', 'year', 'keyword', 'institute', 'recorded_affiliations'])
            links.to_parquet(root / 'institution_links.parquet', index=False)
            paper_keywords = links[['paper_id', 'year', 'keyword']].copy()
            paper_keywords.loc[len(paper_keywords)] = ['p4', 2023, 'capture']
            paper_keywords.to_parquet(root / 'paper_keywords.parquet', index=False)
            pd.DataFrame([(f'p{i}', 2023, f'Paper {i}', f'https://example.test/{i}', 'raw.json')
                          for i in range(1, 5)], columns=['paper_id', 'year', 'title', 'url', 'source_file']).to_parquet(
                              root / 'institution_papers.parquet', index=False)
            (root / 'institution_meta.json').write_text(json.dumps(dict(aggregate_sha256='fixture',
                institutes=2, papers_with_affiliations=3, coverage_by_year={'2023': {'matched_records': 4}})), encoding='utf-8')
            def institute_counts(app):
                app.switch_page('views/institutes.py').run()
                self.assertFalse(app.exception, str(app.exception))
                frame = next(item.value for item in app.dataframe
                             if item.value.columns.tolist() == ['Institute / affiliation', 'Papers', 'Keywords', 'Keyword list'])
                result = dict(zip(frame['Institute / affiliation'], frame.Papers))
                app.switch_page('views/explorer.py').run()
                return result
            def institute_theme_counts(app):
                app.switch_page('views/institutes.py').run()
                app.radio(key='institute_view').set_value('Browse institutes').run()
                self.assertFalse(app.exception, str(app.exception))
                frame = next(item.value for item in app.dataframe
                             if item.value.columns.tolist() == ['Theme', 'Papers', 'Keywords'])
                result = dict(zip(frame.Theme, frame.Papers))
                app.switch_page('views/explorer.py').run()
                return result
            st.cache_resource.clear()
            with patch.object(search, 'INDEX_DIR', str(root)), patch(
                    'sentence_transformers.SentenceTransformer', return_value=object()):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30)
                app.session_state['selected_keyword'] = 'capture'
                app.run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertTrue(any('Partial extraction: 2023' in item.value for item in app.caption))
                self.assertEqual(app.metric[0].value, '40')
                self.assertEqual(dict(app.dataframe[0].value.values), {'United States': 40})
                assert_map_counts(app, {'United States': 40})
                self.assertEqual(institute_counts(app), {'Alpha University': 2})
                self.assertEqual(institute_theme_counts(app), {'capture': 2, 'storage': 1})
                app.select_slider[0].set_value(1.25).run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertEqual(app.metric[0].value, '60')
                self.assertEqual(dict(app.dataframe[0].value.values), {'United States': 40, 'Canada': 20})
                assert_map_counts(app, {'United States': 40, 'Canada': 20})
                self.assertEqual(institute_counts(app), {'Alpha University': 2, 'Beta University': 1})
                self.assertEqual(institute_theme_counts(app), {'capture': 2})
                app.toggle(key='dark_mode').set_value(True).run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertEqual(app.session_state['selected_keyword'], 'capture')
                self.assertEqual(app.metric[0].value, '60')
                self.assertEqual(app.select_slider[0].value, 1.25)
                self.assertEqual(json.loads(app.get('plotly_chart')[0].proto.spec)['layout']['font']['color'], '#ADC0B5')
                self.assertIn('dark', str(app.query_params['theme']))
                assert_map_counts(app, {'United States': 40, 'Canada': 20})
                app.radio[0].set_value('One keyword').run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertEqual(app.metric[0].value, '40')
                self.assertEqual(dict(app.dataframe[0].value.values), {'United States': 40})
                assert_map_counts(app, {'United States': 40})
                fresh_app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=30)
                fresh_app.query_params['theme'] = ['dark']
                fresh_app.run()
                self.assertFalse(fresh_app.exception, str(fresh_app.exception))
                self.assertTrue(fresh_app.toggle(key='dark_mode').value)
                self.assertEqual(institute_counts(app), {'Alpha University': 2})
                app.select_slider[0].set_value(0.75).run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertEqual(app.session_state['selected_keyword'], 'capture')
                self.assertEqual(dict(app.dataframe[0].value.values), {'United States': 40})
                app.switch_page('views/institutes.py').run()
                app.radio(key='institute_view').set_value('Browse institutes').run()
                app.selectbox(key='_institute_pick').set_value('Beta University').run()
                self.assertFalse(app.exception, str(app.exception))
                frame = next(item.value for item in app.dataframe if item.value.columns.tolist() == ['Theme', 'Papers', 'Keywords'])
                self.assertEqual(dict(zip(frame.Theme, frame.Papers)), {'storage': 1})
                keyword_table = next(item.value for item in app.dataframe
                                     if item.value.columns.tolist() == ['Keyword', 'Papers', 'Years'])
                self.assertEqual(keyword_table.Keyword.tolist(), ['storage'])
                self.assertTrue(app.toggle(key='dark_mode').value)
                app.switch_page('views/about.py').run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertTrue(any('Ward distance' in item.value for item in app.markdown))
                app.switch_page('views/trends.py').run()
                self.assertFalse(app.exception, str(app.exception))
                app.switch_page('views/geography.py').run()
                self.assertFalse(app.exception, str(app.exception))
                app.switch_page('views/explorer.py').run()
                self.assertEqual(app.session_state['stats_scope'], 'One keyword')
                self.assertEqual(app.select_slider[0].value, 0.75)
                app.toggle(key='dark_mode').set_value(False).run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertEqual(app.session_state['selected_keyword'], 'capture')
                self.assertEqual(app.metric[0].value, '40')
                self.assertEqual(json.loads(app.get('plotly_chart')[0].proto.spec)['layout']['font']['color'], '#61746D')
                del app.session_state['selected_keyword']
                app.run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertFalse(app.metric)
                # Optional affiliation data must not take down search/maps if incomplete.
                (root / 'institution_links.parquet').unlink()
                metadata = root / 'institution_meta.json'
                payload = json.loads(metadata.read_text())
                payload['refresh'] = True
                metadata.write_text(json.dumps(payload), encoding='utf-8')
                app.session_state['selected_keyword'] = 'capture'
                app.run()
                self.assertFalse(app.exception, str(app.exception))
                self.assertTrue(any('incomplete' in item.value for item in app.warning))
                self.assertEqual(app.metric[0].value, '40')
                assert_map_counts(app, {'United States': 40})
            st.cache_resource.clear()

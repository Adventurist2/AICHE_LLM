import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from countries import country_counts, COUNTRY_CODES
from build_index import build
from search import IndexBundle


class ExplorerRegressionTests(unittest.TestCase):
    def test_aliases_sum_without_guessing_ambiguous_locations(self):
        counts = country_counts({'United States': 33, 'USA': 7, 'Korea': 2})
        self.assertEqual(counts['United States'], 40)
        self.assertEqual(counts['Korea'], 2)
        self.assertNotIn('South Korea', counts)
        self.assertNotIn('Korea', COUNTRY_CODES)

    def test_old_duplicate_country_rows_are_summed(self):
        bundle = IndexBundle(
            pd.DataFrame([{'row_idx': 0, 'total_count': 40}]),
            pd.DataFrame([{'row_idx': 0, 'year': 2023, 'count': 40}]),
            pd.DataFrame([{'row_idx': 0, 'country': 'United States', 'count': 33},
                          {'row_idx': 0, 'country': 'United States', 'count': 7}]),
            np.array([[1.0, 0.0]]), [['capture', 0]], object())
        self.assertEqual(bundle.cluster_row(0)['countries'], {'United States': 40})

    def test_index_counts_and_keyword_selection_across_heights(self):
        model = object()
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            for threshold, groups in [(0.75, [['capture'], ['storage']]),
                                      (1.25, [['capture', 'storage']])]:
                clusters = {}
                for i, members in enumerate(groups):
                    clusters[f'cluster_{i+1}'] = dict(
                        representative=members[0], size=len(members), member_keywords=members,
                        total_count=40*len(members), years={'2023': 40*len(members)},
                        countries={'United States': 33*len(members), 'USA': 7*len(members)})
                source = temp / f'clusters{threshold}.json'
                source.write_text(json.dumps({'meta': {'num_keywords': 2}, 'clusters': clusters}))
                out = temp / str(threshold)
                with patch('build_index.load_leaf_embeddings', return_value=(
                        {'capture': 0, 'storage': 1}, np.array([[1., 0.], [0., 1.]]))):
                    build(threshold, str(source), str(out))
                bundle = IndexBundle.load(str(out), model=model)
                row = bundle.row_for_keyword('capture')
                rec = bundle.cluster_row(row)
                self.assertEqual(rec['countries']['United States'], rec['total_count'])
                self.assertEqual(bundle.clusters.total_count.sum(), 80)
                self.assertEqual(set(bundle.member_keywords(row)), set(groups[0]))
                self.assertFalse(bundle.cluster_country.duplicated(['row_idx', 'country']).any())
                self.assertIs(bundle.model, model)


if __name__ == '__main__':
    unittest.main()

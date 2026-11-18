"""Known-answer paper deduplication, denominators, direction and missingness."""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trend_analysis import build_paper_trends, rank_changes, rank_themes


class PaperTrendTests(unittest.TestCase):
    def setUp(self):
        self.clusters = pd.DataFrame([
            (0, 'cluster_1', 'capture', 2), (1, 'cluster_2', 'storage', 1),
            (2, 'cluster_3', 'new theme', 1)], columns=['row_idx', 'cluster_id', 'representative', 'size'])
        self.members = {'0': ['capture', 'co2 capture'], '1': ['storage'], '2': ['new']}
        self.papers = pd.DataFrame([('a', 2014), ('b', 2014), ('c', 2024), ('d', 2024),
            ('e', 2024), ('f', 2024)], columns=['paper_id', 'year'])
        self.pk = pd.DataFrame([
            ('a', 2014, 'capture'), ('a', 2014, 'co2 capture'), ('a', 2014, 'capture'),
            ('b', 2014, 'storage'), ('c', 2024, 'capture'), ('d', 2024, 'storage'),
            ('e', 2024, 'new'), ('f', 2024, 'new')], columns=['paper_id', 'year', 'keyword'])
        self.data = build_paper_trends(self.clusters, self.members, self.pk, self.papers)

    def test_papers_not_mentions_and_denominator_includes_all_matched_papers(self):
        self.assertEqual(self.data.denominators.to_dict(), {2014: 2, 2024: 4})
        result = rank_themes(self.data, 2014).set_index('representative')
        self.assertEqual(result.loc['capture', 'papers'], 1)
        self.assertEqual(result.loc['capture', 'share_pct'], 50)
        result = rank_changes(self.data, 2014, 2024).set_index('representative')
        self.assertEqual(result.loc['capture', 'change_pp'], -25)
        self.assertEqual(result.loc['new theme', 'change_pp'], 50)
        self.assertEqual(result.loc['new theme', 'start_papers'], 0)

    def test_signed_ranking_filters_and_support(self):
        result = rank_changes(self.data, 2014, 2024)
        self.assertEqual(result.representative.iloc[0], 'new theme')
        self.assertEqual(rank_changes(self.data, 2014, 2024, 'Rising themes').representative.tolist(), ['new theme'])
        self.assertTrue(rank_changes(self.data, 2014, 2024, 'Falling themes').change_pp.lt(0).all())
        self.assertTrue(rank_changes(self.data, 2014, 2024, minimum=3).empty)
        self.assertEqual(rank_themes(self.data, 2024, minimum=2).representative.tolist(), ['new theme'])

    def test_missing_year_is_not_zero_and_invalid_dates_rejected(self):
        for operation in [lambda: rank_themes(self.data, 2020),
                          lambda: rank_changes(self.data, 2014, 2020),
                          lambda: rank_changes(self.data, 2024, 2014),
                          lambda: rank_changes(self.data, 2014, 2014)]:
            with self.assertRaises(ValueError):
                operation()

    def test_both_signs_ranks_large_decline_before_smaller_increases(self):
        pk = pd.DataFrame([('a', 2014, 'capture'), ('b', 2014, 'capture'),
            ('c', 2024, 'storage'), ('d', 2024, 'storage'),
            ('e', 2024, 'new'), ('f', 2024, 'new')], columns=['paper_id', 'year', 'keyword'])
        data = build_paper_trends(self.clusters, self.members, pk, self.papers)
        self.assertEqual(rank_changes(data, 2014, 2024).change_pp.tolist(), [-100, 50, 50])

    def test_inconsistent_source_or_membership_rejected(self):
        bad = self.pk.copy()
        bad.loc[0, 'year'] = 2024
        with self.assertRaises(ValueError):
            build_paper_trends(self.clusters, self.members, bad, self.papers)
        with self.assertRaises(ValueError):
            build_paper_trends(self.clusters, {**self.members, '2': ['capture']}, self.pk, self.papers)
        bad = self.pk.copy()
        bad.loc[0, 'keyword'] = 'unmapped'
        with self.assertRaises(ValueError):
            build_paper_trends(self.clusters, self.members, bad, self.papers)


if __name__ == '__main__':
    unittest.main()

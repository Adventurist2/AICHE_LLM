"""Independent set-based audit of all prepared paper rankings. Run from repo root."""
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from search import INDEX_DIR
from trend_analysis import load_paper_trends, rank_changes, rank_themes


def verify(directories=None):
    root = Path(INDEX_DIR)
    pk = pd.read_parquet(root / 'paper_keywords.parquet')
    paper_year = dict(pd.read_parquet(root / 'institution_papers.parquet')[['paper_id', 'year']].itertuples(index=False, name=None))
    year_sets = defaultdict(set)
    for pid, year, keyword in pk[['paper_id', 'year', 'keyword']].itertuples(index=False, name=None):
        assert paper_year[pid] == year
        year_sets[year].add(pid)
    start, end = min(year_sets), max(year_sets)
    directories = list(directories) if directories is not None else list(root.glob('dt*'))
    for directory in sorted(directories, key=lambda p: float(p.name[2:])):
        meta = json.loads((directory / 'meta.json').read_text(encoding='utf-8'))
        data = load_paper_trends(directory, meta['aggregate_sha256'])
        owner = {keyword: int(row) for row, keywords in data.members.items() for keyword in keywords}
        gold = defaultdict(set)
        for pid, year, keyword in pk[['paper_id', 'year', 'keyword']].itertuples(index=False, name=None):
            gold[owner[keyword], year].add(pid)
        for year in year_sets:
            ranked = rank_themes(data, year)
            assert len(ranked) == sum(y == year for row, y in gold)
            for row in ranked.itertuples(index=False):
                count = len(gold[row.row_idx, year])
                assert row.papers == count
                assert abs(row.share_pct - 100 * count / len(year_sets[year])) < 1e-10
        changes = rank_changes(data, start, end)
        assert changes.absolute_change_pp.is_monotonic_decreasing
        for row in changes.itertuples(index=False):
            assert row.start_papers == len(gold[row.row_idx, start])
            assert row.end_papers == len(gold[row.row_idx, end])
            expected = 100 * len(gold[row.row_idx, end]) / len(year_sets[end]) - 100 * len(gold[row.row_idx, start]) / len(year_sets[start])
            assert abs(row.change_pp - expected) < 1e-10
        assert rank_changes(data, start, end, 'Rising themes').change_pp.gt(0).all()
        assert rank_changes(data, start, end, 'Falling themes').change_pp.lt(0).all()
        print(f"Height {meta['threshold']:.2f}: all {len(year_sets)} observed-year rankings and {len(changes):,} endpoint changes match independent paper-ID sets")


if __name__ == '__main__':
    verify()

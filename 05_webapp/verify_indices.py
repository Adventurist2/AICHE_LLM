"""Verify every theme's index totals against the keyword snapshot, at every height."""
import json
from collections import Counter
from pathlib import Path

import numpy as np
from countries import country_counts
from search import IndexBundle, INDEX_DIR


def verify():
    snapshot = json.loads(Path(INDEX_DIR, 'keyword_stats.json').read_text(encoding='utf-8'))
    stats = snapshot['keywords']
    total = sum(rec['total_count'] for rec in stats.values())
    paths = sorted(Path(INDEX_DIR).glob('dt*/meta.json'))
    assert paths, 'No threshold indices found'
    previous = None
    for path in sorted(paths, key=lambda p: float(json.loads(p.read_text())['threshold'])):
        meta = json.loads(path.read_text(encoding='utf-8'))
        assert meta['aggregate_sha256'] == snapshot['aggregate_sha256']
        bundle = IndexBundle.load(str(path.parent), model=object())
        all_members = [kw for members in bundle.members.values() for kw in members]
        assert len(all_members) == len(set(all_members)) == len(stats)
        assert set(all_members) == set(stats)
        assert int(bundle.clusters.total_count.sum()) == total
        assert not bundle.cluster_country.duplicated(['row_idx', 'country']).any()
        assert not bundle.cluster_year.duplicated(['row_idx', 'year']).any()
        assert np.allclose(np.linalg.norm(bundle.embeddings, axis=1), 1, atol=1e-5)
        countries = {int(row): dict(zip(group.country, group['count']))
                     for row, group in bundle.cluster_country.groupby('row_idx')}
        years = {int(row): dict(zip(group.year.astype(str), group['count']))
                 for row, group in bundle.cluster_year.groupby('row_idx')}
        rows = {int(rec.row_idx): rec for rec in bundle.clusters.itertuples()}
        keyword_rows = {}
        for key, members in bundle.members.items():
            row = int(key)
            expected_countries, expected_years = Counter(), Counter()
            for kw in members:
                expected_countries.update(country_counts(stats[kw]['countries']))
                expected_years.update(stats[kw]['years'])
                keyword_rows[kw] = row
            assert rows[row].total_count == sum(stats[kw]['total_count'] for kw in members)
            assert rows[row].size == len(members)
            assert countries.get(row, {}) == dict(expected_countries), (meta['threshold'], row, 'countries')
            assert years.get(row, {}) == dict(expected_years), (meta['threshold'], row, 'years')
        if previous is not None:
            # Raising the cut height can merge a cluster, but cannot split it.
            parents = {}
            for kw, old_row in previous.items():
                parents.setdefault(old_row, keyword_rows[kw])
                assert parents[old_row] == keyword_rows[kw]
        previous = keyword_rows
        print(f"Height {meta['threshold']:.2f}: {len(rows):,} themes; {len(stats):,} keywords; "
              f"{total:,} mentions; all country/year counts and hierarchy verified")


if __name__ == '__main__':
    verify()

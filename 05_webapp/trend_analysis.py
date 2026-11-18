"""Paper-level theme prevalence and endpoint changes; independent of Streamlit."""
from dataclasses import dataclass
import json
from pathlib import Path

import pandas as pd


@dataclass
class PaperTrends:
    clusters: pd.DataFrame
    counts: pd.DataFrame
    denominators: pd.Series
    pairs: pd.DataFrame
    papers: pd.DataFrame
    members: dict


def build_paper_trends(clusters, members, paper_keywords, papers):
    if papers.paper_id.isna().any() or not papers.paper_id.is_unique:
        raise ValueError('Source paper IDs must be present and unique.')
    pk = paper_keywords[['paper_id', 'year', 'keyword']].drop_duplicates().copy()
    if pk.isna().any().any():
        raise ValueError('Paper/keyword/year records contain missing values.')
    checked = pk.merge(papers[['paper_id', 'year']], on='paper_id', how='left',
                       validate='many_to_one', suffixes=('', '_source'))
    if checked.year_source.isna().any() or not checked.year.eq(checked.year_source).all():
        raise ValueError('Keyword records do not match the source paper IDs and years.')
    mapping = pd.DataFrame([(int(row), kw) for row, values in members.items() for kw in values],
                           columns=['row_idx', 'keyword'])
    if not clusters.row_idx.is_unique or not mapping.keyword.is_unique:
        raise ValueError('Each keyword must belong to exactly one theme at this height.')
    if set(mapping.row_idx) != set(clusters.row_idx):
        raise ValueError('Theme members and cluster rows do not match.')
    sizes = mapping.groupby('row_idx').size().reindex(clusters.row_idx).to_numpy()
    if not (sizes == clusters['size'].to_numpy()).all():
        raise ValueError('Theme member counts do not match the cluster metadata.')
    joined = pk.merge(mapping, on='keyword', how='left', validate='many_to_one')
    if joined.row_idx.isna().any():
        raise ValueError('Some paper keywords are absent from this clustering snapshot.')
    pairs = joined[['row_idx', 'year', 'paper_id']].drop_duplicates()
    counts = pairs.groupby(['row_idx', 'year']).size().rename('papers').reset_index()
    denominators = pk.groupby('year').paper_id.nunique().sort_index()
    if denominators.empty:
        raise ValueError('No source-matched, keyword-bearing papers are available.')
    counts['share_pct'] = 100 * counts.papers / counts.year.map(denominators)
    if counts.share_pct.gt(100).any():
        raise ValueError('Theme paper counts exceed the eligible paper denominator.')
    return PaperTrends(clusters.copy(), counts, denominators, pairs, papers.copy(), members)


def load_paper_trends(directory, expected_sha):
    directory = Path(directory)
    root = directory.parent
    meta = json.loads((directory / 'meta.json').read_text(encoding='utf-8'))
    institution_meta = json.loads((root / 'institution_meta.json').read_text(encoding='utf-8'))
    if not expected_sha or any(m.get('aggregate_sha256') != expected_sha for m in (meta, institution_meta)):
        raise ValueError('Paper records and clustering belong to different snapshots.')
    return build_paper_trends(pd.read_parquet(directory / 'clusters.parquet'),
        json.loads((directory / 'members.json').read_text(encoding='utf-8')),
        pd.read_parquet(root / 'paper_keywords.parquet'),
        pd.read_parquet(root / 'institution_papers.parquet'))


def _year(data, year):
    if year not in data.denominators.index:
        raise ValueError(f'{year} has no eligible paper observations; it is not a zero-count year.')
    return data.counts.loc[data.counts.year.eq(year)].set_index('row_idx')


def rank_themes(data, year, minimum=1):
    if minimum < 1:
        raise ValueError('Minimum paper support must be positive.')
    result = data.clusters.merge(_year(data, year)[['papers', 'share_pct']],
                                 left_on='row_idx', right_index=True, how='left')
    result[['papers', 'share_pct']] = result[['papers', 'share_pct']].fillna(0)
    result = result[result.papers.ge(minimum)].sort_values(
        ['papers', 'cluster_id'], ascending=[False, True]).reset_index(drop=True)
    result['papers'] = result.papers.astype(int)
    result.insert(0, 'rank', range(1, len(result) + 1))
    return result


def rank_changes(data, start, end, direction='Largest changes', minimum=1):
    if start >= end:
        raise ValueError('Choose an end year after the start year.')
    if minimum < 1:
        raise ValueError('Minimum paper support must be positive.')
    if direction not in ('Largest changes', 'Rising themes', 'Falling themes'):
        raise ValueError('Unknown change direction.')
    result = data.clusters.copy()
    for year, prefix in [(start, 'start'), (end, 'end')]:
        values = _year(data, year)
        result[f'{prefix}_papers'] = result.row_idx.map(values.papers).fillna(0).astype(int)
        result[f'{prefix}_share_pct'] = result.row_idx.map(values.share_pct).fillna(0)
    result['change_pp'] = result.end_share_pct - result.start_share_pct
    result['absolute_change_pp'] = result.change_pp.abs()
    result['total_papers'] = result.row_idx.map(data.counts.groupby('row_idx').papers.sum()).fillna(0).astype(int)
    result = result[(result.start_papers + result.end_papers).ge(minimum)]
    if direction == 'Rising themes':
        result = result[result.change_pp.gt(0)]
    elif direction == 'Falling themes':
        result = result[result.change_pp.lt(0)]
    result = result.sort_values(['absolute_change_pp', 'total_papers', 'cluster_id'],
                                ascending=[False, False, True]).reset_index(drop=True)
    result.insert(0, 'rank', range(1, len(result) + 1))
    return result

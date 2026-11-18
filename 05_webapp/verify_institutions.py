"""Audit shared affiliation tables, source provenance and the complete CSV export."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import re

import pandas as pd

from institutions import ROOT, SOURCE_DIRS, clean, invalid_affiliation_reason, institute_summary, INVALID_PAPER_TITLES
from search import INDEX_DIR


def verify(aggregate_path=ROOT / '02_extraction/aggregate.json', source_only=False):
    directory = Path(INDEX_DIR)
    meta = json.loads((directory / 'institution_meta.json').read_text(encoding='utf-8'))
    aggregate = json.loads(Path(aggregate_path).read_text(encoding='utf-8'))
    signature = hashlib.sha256(json.dumps(aggregate, sort_keys=True).encode()).hexdigest()
    assert meta['aggregate_sha256'] == signature, 'Institute snapshot does not match the aggregate'
    links = pd.read_parquet(directory / 'institution_links.parquet')
    papers = pd.read_parquet(directory / 'institution_papers.parquet')
    keywords = pd.read_parquet(directory / 'paper_keywords.parquet')
    assert not papers.paper_id.duplicated().any()
    assert not keywords.duplicated(['paper_id', 'keyword']).any()
    assert not links.duplicated(['paper_id', 'keyword', 'institute']).any()
    assert set(keywords.keyword) <= set(aggregate)
    assert set(links.keyword) <= set(aggregate)
    assert set(keywords.paper_id) == set(papers.paper_id)
    assert set(links.paper_id) <= set(papers.paper_id)
    assert len(links) == meta['links']
    assert len(papers) == meta['matched_papers']
    assert links.paper_id.nunique() == meta['papers_with_affiliations']
    assert links.keyword.nunique() == meta['linked_keywords']
    assert links.institute.nunique() == meta['institutes']
    assert not links[['keyword', 'institute', 'recorded_affiliations']].isna().any().any()
    assert not links.institute.str.strip().eq('').any()
    for frame in (links, keywords):
        joined = frame[['paper_id', 'year']].drop_duplicates().merge(
            papers[['paper_id', 'year']], on='paper_id', suffixes=('_link', '_paper'), validate='many_to_one')
        assert (joined.year_link == joined.year_paper).all(), 'Cross-year paper attribution'
    valid_pairs = keywords[['paper_id', 'keyword']].assign(found=True)
    assert links.merge(valid_pairs, on=['paper_id', 'keyword'], how='left').found.notna().all()
    # Check recorded text against original author metadata, independently of name resolution.
    original = defaultdict(set)
    source_titles = defaultdict(set)
    titles_with_affiliations = defaultdict(set)
    source_matches = defaultdict(set)
    for year, folders in SOURCE_DIRS.items():
        for folder in folders:
            for path in (ROOT / folder).glob('*.json'):
                records = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(records, list):
                    continue
                for ordinal, record in enumerate(records):
                    if not isinstance(record, dict):
                        continue
                    url = clean(record.get('url'))
                    url_year = re.search(r'/aiche/(\d{4})/', url)
                    if url_year and url_year.group(1) != str(year):
                        continue
                    title = clean(record.get('title') or record.get('topic')).casefold()
                    if not title or title in INVALID_PAPER_TITLES or re.search(
                            r'\.(pdf|docx?|pptx?)(?:$|[?#])', url, re.I):
                        continue
                    identity = f'{year}:{url}' if url else f'{year}:{path.name}:{ordinal}'
                    # Read original author fields directly, without the builder's parser.
                    raw_values = [author.get('affiliation', '') for author in record.get(
                        'authors_structured', []) if isinstance(author, dict)]
                    for value in list(record.get('authors', []) or []) + [record.get('presenting_author', '')]:
                        if isinstance(value, str) and '|' in value:
                            raw_values.append(value.partition('|')[2])
                    values = {clean(value) for value in raw_values}
                    original[identity].update(values)
                    for alias in {clean(record.get('title')), clean(record.get('topic'))}:
                        if alias and alias.casefold() not in INVALID_PAPER_TITLES:
                            source_titles[identity].add(alias.casefold())
                            source_matches[(year, path.name, alias.casefold())].add(identity)
                    if any(invalid_affiliation_reason(value) is None for value in values):
                        titles_with_affiliations[identity].add(re.sub(r'^\d+[a-z]+-\s*', '', title))
    for paper in papers.itertuples(index=False):
        assert clean(paper.title).casefold() in source_titles[paper.paper_id], paper.paper_id
        assert len(titles_with_affiliations[paper.paper_id]) <= 1, 'Conflicting titled records carry affiliations'
    # Independently resolve every keyword reference through year, file and title.
    expected_pairs = set()
    for keyword, entry in aggregate.items():
        for year, refs in entry.get('papers_by_year', {}).items():
            for ref in refs:
                chunk = ref.get('source_file', '').removeprefix('ext_')
                raw = re.sub(r'_p\d+(?=\.json$)', '', chunk)
                title = clean(ref.get('title')).casefold()
                candidates = source_matches.get((str(year), raw, title), set())
                if not candidates:
                    candidates = source_matches.get((str(year), chunk, title), set())
                if len(candidates) == 1:
                    expected_pairs.add((next(iter(candidates)), keyword))
    assert set(keywords[['paper_id', 'keyword']].itertuples(index=False, name=None)) == expected_pairs, (
        'Keyword-to-paper links differ from original year/file/title matches')
    for record in links[['paper_id', 'recorded_affiliations']].drop_duplicates().itertuples(index=False):
        assert set(record.recorded_affiliations.split('\n')) <= original[record.paper_id], record.paper_id
    for record in links[['institute', 'recorded_affiliations']].drop_duplicates().itertuples(index=False):
        assert invalid_affiliation_reason(record.institute) is None, f'Invalid institute: {record.institute}'
        # A shortened display name must be an entire comma-delimited original name.
        for value in record.recorded_affiliations.split('\n'):
            assert invalid_affiliation_reason(value) is None, f'Invalid affiliation: {value}'
            parts = value.casefold().split(', ')
            assert any(', '.join(parts[start:end]) == record.institute.casefold()
                       for start in range(len(parts)) for end in range(start + 1, len(parts) + 1)), (
                           f'Institute display name unsupported by original affiliation: {record.institute}')
    expected = links.groupby(['institute', 'keyword']).agg(
        Papers=('paper_id', 'nunique'), Years=('year', lambda s: ', '.join(map(str, sorted(set(s))))))
    expected = expected.rename_axis(['Institute / affiliation', 'Keyword']).reset_index()
    exported = pd.read_csv(directory / 'institute_keywords.csv', dtype={'Years': str}, keep_default_na=False)
    pd.testing.assert_frame_equal(exported, expected, check_dtype=False)
    unresolved = pd.read_csv(directory / 'institution_unmatched_records.csv')
    assert len(unresolved) == sum(
        counts.get('source_or_title_not_found', 0) + counts.get('ambiguous_title', 0)
        for counts in meta['coverage_by_year'].values())
    for counts in meta['coverage_by_year'].values():
        assert counts['referenced_records'] == counts.get('matched_records', 0) + counts.get(
            'source_or_title_not_found', 0) + counts.get('ambiguous_title', 0)
        assert counts.get('records_with_affiliations', 0) <= counts.get('matched_records', 0)
    excluded = pd.read_csv(directory / 'institution_excluded_affiliations.csv', keep_default_na=False)
    assert len(excluded) == meta['excluded_affiliation_records']
    for row in excluded.itertuples(index=False):
        assert row.recorded_affiliation in original[row.paper_id]
        assert invalid_affiliation_reason(row.recorded_affiliation) == row.reason
    if source_only:
        print(f'Verified {len(links):,} source-backed attribution links, {len(papers):,} matched papers '
              f'and all {len(expected_pairs):,} keyword/paper pairs before clustering completes.')
        return
    # Save a reviewable source trail for the selection currently being reviewed.
    from search import IndexBundle
    bundle = IndexBundle.load(str(directory / 'dt1'), model=object())
    members = bundle.member_keywords(bundle.row_for_keyword('co2 capture'))
    selected = links[links.keyword.isin(members)]
    summary = institute_summary(selected)
    evidence = selected.merge(papers, on=['paper_id', 'year'], validate='many_to_one')
    evidence.to_csv(directory / 'institution_validation_evidence.csv', index=False, encoding='utf-8-sig')
    matched = keywords[keywords.keyword.isin(members)].paper_id.nunique()
    report = [
        '# Institute validation', '',
        'All checks passed against the saved original conference scrape and keyword aggregate.', '',
        f'- {len(links):,} institute/keyword/paper links audited.',
        f'- {len(papers):,} matched papers; {links.institute.nunique():,} recorded institute/affiliation names.',
        f'- All {len(expected_pairs):,} keyword/paper pairs independently matched by year, source file and exact title.',
        '- Every original affiliation occurs in the source author fields; every shortened institute name is supported by an entire comma-delimited source name.',
        '- Duplicate links, cross-year matches and unsupported contact values are absent.',
        f'- {len(exported):,} exported institute/keyword pairs match distinct-paper counts.',
        f'- {len(excluded):,} invalid contact affiliation records excluded; see institution_excluded_affiliations.csv.', '',
        '## CO2 capture, whole theme, threshold 1.00', '',
        f'{len(members)} keywords; {matched} matched papers; {selected.paper_id.nunique()} with valid affiliations; {len(summary)} institute/affiliation names.', '',
        '| Institute / affiliation | Distinct papers |', '|---|---:|',
        *[f'| {row["Institute / affiliation"]} | {row["Papers"]} |' for row in summary.head(12).to_dict('records')], '',
        'The full source trail is in institution_validation_evidence.csv, including original affiliation text, paper titles, years, URLs and source files.', '',
        '## Limits', '',
        'This validates attribution to the stored conference records, not an independently curated institution registry. Original scrape errors and keyword extraction errors can remain. Department/location strings and spelling variants may remain separate. A whole theme includes related cluster keywords; use One keyword for exact-keyword attribution. Missing or ambiguous paper matches are excluded, and affiliations are not inferred.',
    ]
    (directory / 'institution_validation.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    print(f"Verified {len(links):,} institute/keyword/paper links, {len(papers):,} matched papers, "
          f"{len(exported):,} exported institute/keyword pairs and original affiliation provenance.")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aggregate', default=str(ROOT / '02_extraction/aggregate.json'))
    parser.add_argument('--source-only', action='store_true', help='Audit affiliations before search indices are ready')
    args = parser.parse_args()
    verify(args.aggregate, args.source_only)

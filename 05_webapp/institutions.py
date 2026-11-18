"""Link the aggregate's keywords to recorded paper affiliations, without inference."""
import argparse
from collections import Counter, defaultdict
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = {
    '2014': ['01_scraping/raw/aiche_file_2014', '01_scraping/chunked/aiche_file_2014_output'],
    '2015': ['aiche_file_2015', 'archive/catch/aiche_file_2015',
             'aiche_file_2015_output', 'archive/completed/aiche_file_2015_output'],
    '2016': ['01_scraping/raw/2016', '01_scraping/chunked/aiche_file_2016_output'],
    '2017': ['01_scraping/raw/UGP_2017', 'aiche_file_2017_output'],
    '2018': ['01_scraping/raw/aiche_file_2018', '01_scraping/chunked/aiche_file_2018_output'],
    '2019': ['archive/UGP-side-project/UGP_2019_reparsed'],
    '2020': ['01_scraping/raw/UGP_2020'],
    '2021': ['01_scraping/raw/UGP_2021', 'aiche_file_2021_output', 'archive/completed/aiche_file_2021_output'],
    '2022': ['archive/completed/aiche_file_2022_output'],
    '2023': ['01_scraping/raw/aiche_file', '01_scraping/chunked/aiche_file_output'],
    '2024': ['01_scraping/raw/aiche_file_2024', '01_scraping/chunked/aiche_file_2024_output'],
}
UNKNOWN = {'', 'unknown', 'not available', 'not found', 'unavailable', 'not provided',
           'affiliation not available', 'n/a', 'none', 'university unavailable', 'not indexed'}
INVALID_PAPER_TITLES = {'error scraping', '503 service unavailable'}


def clean(value):
    return ' '.join(html.unescape(unicodedata.normalize('NFKC', str(value or ''))).split()).strip(' |')


def recorded_affiliations(paper):
    values = [a.get('affiliation', '') for a in paper.get('authors_structured', []) if isinstance(a, dict)]
    # Older scrapers sometimes retained only the "name | affiliation" string.
    for value in list(paper.get('authors', []) or []) + [paper.get('presenting_author', '')]:
        if isinstance(value, str) and '|' in value:
            values.append(value.split('|', 1)[1])
    return {clean(v) for v in values}


def invalid_affiliation_reason(value):
    value = clean(value)
    if value.casefold() in UNKNOWN:
        return 'missing_or_placeholder'
    if not any(character.isalpha() for character in value):
        return 'number_or_punctuation_only'
    # Contact-only and contact-led location strings do not identify an institute.
    first = value.split(',', 1)[0].strip()
    if re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', first):
        return 'email_contact'
    if re.match(r'^(?:https?://|www\.)', value, re.I):
        return 'web_contact'
    return None


def affiliations(paper):
    return {v for v in recorded_affiliations(paper) if invalid_affiliation_reason(v) is None}


class AffiliationNames:
    """Use exact organization names already present in the newer source records.

    Strip a department/location only when an entire comma-delimited organization
    name matches. Unrecognized affiliations remain intact; no fuzzy matching.
    """
    def __init__(self, values):
        self.names = {}
        frequency = Counter(values)
        for value in sorted(frequency, key=lambda v: (-frequency[v], v)):
            value = clean(value)
            # Campus qualifiers containing a comma must remain part of the name.
            campus = re.match(r'^University of California, [^,]+$', value, re.I)
            if value.casefold() in ('university of california', 'university of wisconsin'):
                continue
            if not re.search(r'\b(university|universit[eé]|college|institute|laborator\w*|polytechnic|academy|'
                             r'corporation|company|inc\.?|llc|ltd|gmbh|research cent(?:er|re))\b', value, re.I):
                continue
            if (',' not in value or campus) and not re.search(
                    r'\b(department|school of|faculty of|division of)\b', value, re.I):
                self.names.setdefault(value.casefold(), value)

    def resolve(self, value):
        value = clean(value)
        parts = value.split(', ')
        candidates = []
        for start in range(len(parts)):
            for end in range(start + 1, len(parts) + 1):
                key = ', '.join(parts[start:end]).casefold()
                if key in self.names:
                    candidates.append(self.names[key])
        # Two separate recognized organizations in one affiliation are ambiguous.
        maximal = [c for c in set(candidates) if not any(
            c.casefold() in other.casefold() and c != other for other in candidates)]
        return maximal[0] if len(maximal) == 1 else value


def institute_summary(links, keywords=None):
    selected = links if keywords is None else links[links.keyword.isin(keywords)]
    if selected.empty:
        return pd.DataFrame(columns=['Institute / affiliation', 'Papers', 'Keywords', 'Keyword list'])
    table = selected.groupby('institute').agg(
        Papers=('paper_id', 'nunique'), Keywords=('keyword', 'nunique'),
        **{'Keyword list': ('keyword', lambda s: ', '.join(sorted(set(s))))})
    return table.rename_axis('Institute / affiliation').reset_index().sort_values(
        ['Papers', 'Institute / affiliation'], ascending=[False, True]).reset_index(drop=True)


def keyword_summary(links, institute):
    selected = links[links.institute == institute]
    table = selected.groupby('keyword').agg(
        Papers=('paper_id', 'nunique'), Years=('year', lambda s: ', '.join(map(str, sorted(set(s))))))
    return table.rename_axis('Keyword').reset_index().sort_values(
        ['Papers', 'Keyword'], ascending=[False, True]).reset_index(drop=True)


def build_institutions(aggregate_path, out_dir, source_dirs=None, root=ROOT):
    aggregate = json.loads(Path(aggregate_path).read_text(encoding='utf-8'))
    signature = hashlib.sha256(json.dumps(aggregate, sort_keys=True).encode()).hexdigest()
    sources = defaultdict(lambda: defaultdict(dict))
    named_affiliations = Counter()
    paper_data = {}
    excluded_affiliations = {}
    for year, folders in (source_dirs or SOURCE_DIRS).items():
        for folder in folders:
            for path in sorted((Path(root) / folder).glob('*.json')):
                records = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(records, list):
                    continue
                for ordinal, paper in enumerate(records):
                    if not isinstance(paper, dict):
                        continue
                    title = clean(paper.get('title') or paper.get('topic'))
                    url = clean(paper.get('url'))
                    url_year = re.search(r'/aiche/(\d{4})/', url)
                    if url_year and url_year.group(1) != str(year):
                        continue
                    # Some historical scrapes mislabeled abstract attachment URLs
                    # with a neighboring presentation's title. They are not papers.
                    if not title or title.casefold() in INVALID_PAPER_TITLES or re.search(
                            r'\.(pdf|docx?|pptx?)(?:$|[?#])', url, re.I):
                        continue
                    # A source file + row is a stable conservative fallback, never title alone.
                    identity = f'{year}:{url}' if url else f'{year}:{path.name}:{ordinal}'
                    for value in recorded_affiliations(paper):
                        reason = invalid_affiliation_reason(value)
                        if reason and reason != 'missing_or_placeholder':
                            excluded_affiliations.setdefault((identity, value), dict(
                                paper_id=identity, year=int(year), title=title,
                                recorded_affiliation=value, reason=reason,
                                source_file=str(path.relative_to(root))))
                    affs = affiliations(paper)
                    if year in ('2018', '2023', '2024'):
                        named_affiliations.update(affs)
                    # Scrapers keep both an API title and a presentation-numbered
                    # topic. Either exact recorded title can identify this paper.
                    for alias in {clean(paper.get('title')), clean(paper.get('topic'))}:
                        if alias and alias.casefold() not in INVALID_PAPER_TITLES:
                            sources[(year, path.name)][alias.casefold()][identity] = True
                    if identity not in paper_data:
                        paper_data[identity] = dict(paper_id=identity, year=int(year), title=title,
                                                    url=url, source_file=str(path.relative_to(root)), affiliations=set())
                    paper_data[identity]['affiliations'].update(affs)

    names = AffiliationNames(named_affiliations)
    references = defaultdict(set)
    for keyword, record in aggregate.items():
        for year, papers in record.get('papers_by_year', {}).items():
            for ref in papers:
                references[(str(year), ref.get('source_file', ''), clean(ref.get('title')).casefold())].add(keyword)
    paper_keywords = set()
    coverage = defaultdict(Counter)
    unresolved = []
    for (year, extracted_file, title), keywords in sorted(references.items()):
        coverage[year]['referenced_records'] += 1
        chunk = extracted_file.removeprefix('ext_')
        raw = re.sub(r'_p\d+(?=\.json$)', '', chunk)
        candidates = sources.get((year, raw), {}).get(title, {})
        if not candidates:
            candidates = sources.get((year, chunk), {}).get(title, {})
        if len(candidates) != 1:
            reason = 'ambiguous_title' if candidates else 'source_or_title_not_found'
            coverage[year][reason] += 1
            unresolved.append(dict(year=year, source_file=extracted_file, title=title, reason=reason))
            continue
        identity = next(iter(candidates))
        coverage[year]['matched_records'] += 1
        if paper_data[identity]['affiliations']:
            coverage[year]['records_with_affiliations'] += 1
        for keyword in keywords:
            paper_keywords.add((identity, keyword))

    keyword_rows = []
    link_rows = []
    used_papers = set()
    for identity, keyword in sorted(paper_keywords):
        paper = paper_data[identity]
        used_papers.add(identity)
        keyword_rows.append((identity, paper['year'], keyword))
        grouped_affs = defaultdict(set)
        for value in paper['affiliations']:
            grouped_affs[names.resolve(value)].add(value)
        for institute, original in sorted(grouped_affs.items()):
            link_rows.append((identity, paper['year'], keyword, institute, '\n'.join(sorted(original))))
    links = pd.DataFrame(link_rows, columns=['paper_id', 'year', 'keyword', 'institute', 'recorded_affiliations'])
    keywords = pd.DataFrame(keyword_rows, columns=['paper_id', 'year', 'keyword'])
    papers = pd.DataFrame([{k: v for k, v in paper_data[identity].items() if k != 'affiliations'}
                           for identity in sorted(used_papers)],
                          columns=['paper_id', 'year', 'title', 'url', 'source_file'])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in [('institution_links', links), ('institution_papers', papers), ('paper_keywords', keywords)]:
        temp = out / f'{name}.tmp.parquet'
        frame.to_parquet(temp, index=False)
        temp.replace(out / f'{name}.parquet')
    summary = links.groupby(['institute', 'keyword']).agg(
        Papers=('paper_id', 'nunique'), Years=('year', lambda s: ', '.join(map(str, sorted(set(s))))))
    summary.rename_axis(['Institute / affiliation', 'Keyword']).reset_index().to_csv(
        out / 'institute_keywords.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(unresolved, columns=['year', 'source_file', 'title', 'reason']).to_csv(
        out / 'institution_unmatched_records.csv', index=False, encoding='utf-8-sig')
    excluded = [row for row in excluded_affiliations.values() if row['paper_id'] in used_papers]
    pd.DataFrame(excluded, columns=['paper_id', 'year', 'title', 'recorded_affiliation', 'reason', 'source_file']).to_csv(
        out / 'institution_excluded_affiliations.csv', index=False, encoding='utf-8-sig')
    meta = dict(aggregate_sha256=signature, institutes=links.institute.nunique(),
                matched_papers=len(papers), papers_with_affiliations=links.paper_id.nunique(),
                linked_keywords=links.keyword.nunique(), links=len(links),
                excluded_affiliation_records=len(excluded),
                coverage_by_year={y: dict(counts) for y, counts in sorted(coverage.items())},
                normalization='Exact organization names from 2018/2023/2024 records; otherwise recorded affiliation.')
    temp = out / 'institution_meta.tmp'
    temp.write_text(json.dumps(meta, indent=2), encoding='utf-8')
    temp.replace(out / 'institution_meta.json')
    print(json.dumps(meta, indent=2))
    return meta


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aggregate', default=str(ROOT / '02_extraction/aggregate.json'))
    parser.add_argument('--out-dir', default=str(ROOT / '05_webapp/index'))
    args = parser.parse_args()
    build_institutions(args.aggregate, args.out_dir)

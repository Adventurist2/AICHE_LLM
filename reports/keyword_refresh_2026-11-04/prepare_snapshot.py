"""Freeze completed extraction outputs, excluding duplicate wrong-year batches."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil

JOB = Path(__file__).resolve().parent
ROOT = JOB.parents[1]
inputs = {'2017': ROOT / 'aiche_file_2017_output',
          '2021': ROOT / 'archive/completed/aiche_file_2021_output',
          '2022': ROOT / 'archive/completed/aiche_file_2022_output'}
manifest = dict(files=[], excluded=[], years={}, partial_years=[2017])
assert not (JOB / 'input_manifest.json').exists(), 'Snapshot already exists'
for directory in sorted((ROOT / 'groq').glob('extracted_results*')):
    if not directory.is_dir():
        continue
    match = re.fullmatch(r'extracted_results(?:_(\d{4}))?', directory.name)
    if not match:
        continue
    year = match.group(1) or '2023'
    counts = Counter()
    for path in sorted(directory.glob('*.json')):
        content = path.read_bytes()
        records = json.loads(content.decode('utf-8-sig'))
        if isinstance(records, dict):
            records = [records]
        assert isinstance(records, list) and all(isinstance(r, dict) for r in records), path
        if year in inputs:
            source = inputs[year] / path.name.removeprefix('ext_')
            raw = json.loads(source.read_text(encoding='utf-8-sig'))
            years = {m.group(1) for r in raw
                     if (m := re.search(r'/aiche/(\d{4})/', str(r.get('url', ''))))}
            assert len(years) <= 1, f'Mixed-year input batch: {source}'
            if years and years != {year}:
                actual = next(iter(years))
                canonical = ROOT / 'groq' / f'extracted_results_{actual}' / path.name
                assert canonical.exists(), f'Wrong-year batch has no correctly filed counterpart: {path}'
                manifest['excluded'].append(dict(source=str(path.relative_to(ROOT)), actual_year=actual,
                    canonical=str(canonical.relative_to(ROOT)), reason='duplicate_wrong_year_folder',
                    sha256=hashlib.sha256(content).hexdigest(), records=len(records)))
                continue
        for record in records:
            values = record.get('keywords') or []
            assert isinstance(values, (str, list)), path
            assert all(isinstance(value, str) for value in ([values] if isinstance(values, str) else values)), path
        target = JOB / 'extractions' / directory.name / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        manifest['files'].append(dict(source=str(path.relative_to(ROOT)), snapshot=str(target.relative_to(ROOT)),
            sha256=hashlib.sha256(content).hexdigest(), bytes=len(content), year=year))
        counts['files'] += 1
        counts['records'] += len(records)
        counts['with_keywords'] += sum(bool(r.get('keywords')) for r in records)
    manifest['years'][year] = dict(counts)
shutil.copy2(ROOT / '02_extraction/aggregate.json', JOB / 'aggregate_before.json')
(JOB / 'input_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(dict(years=manifest['years'], excluded_batches=len(manifest['excluded'])), indent=2))

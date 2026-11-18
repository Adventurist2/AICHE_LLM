"""Build every slider index and a shared keyword-statistics snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
from build_index import build, OUT_DIR
from institutions import build_institutions


def prepare(aggregate_path, clusters_dir, output_dir=OUT_DIR):
    aggregate = json.loads(Path(aggregate_path).read_text(encoding='utf-8'))
    signature = hashlib.sha256(json.dumps(aggregate, sort_keys=True).encode()).hexdigest()
    files = sorted(Path(clusters_dir).glob('clusters_dt*.json'))
    if not files:
        raise ValueError('No cluster results found')
    for path in files:
        data = json.loads(path.read_text(encoding='utf-8'))
        if data['meta'].get('aggregate_sha256') != signature:
            raise ValueError(f'{path} belongs to a different aggregate; regenerate clustering first')
    for path in files:
        threshold = float(path.stem.removeprefix('clusters_dt'))
        build(threshold, str(path), str(Path(output_dir) / f'dt{threshold:g}'))
    stats = {kw: {key: rec.get(key, {}) for key in ('total_count', 'years', 'countries')}
             for kw, rec in aggregate.items()}
    path = Path(output_dir) / 'keyword_stats.json'
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'aggregate_sha256': signature, 'keywords': stats}), encoding='utf-8')
    tmp.replace(path)
    build_institutions(aggregate_path, output_dir)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--aggregate', default='02_extraction/aggregate.json')
    parser.add_argument('--clusters-dir', default='04_clustering/explorer_results')
    parser.add_argument('--output-dir', default=OUT_DIR, help='Build a separate snapshot before publication')
    args = parser.parse_args()
    prepare(args.aggregate, args.clusters_dir, args.output_dir)

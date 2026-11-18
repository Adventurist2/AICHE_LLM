#!/usr/bin/env python3
"""
Build the search/dashboard index consumed by app.py.

Reads an explorer_results/clusters_dt<T>.json (produced by
04_clustering/cluster_keywords.py) plus the leaf-keyword embeddings cached
during that run, and writes artifacts into 05_webapp/index/dt<T>/:

  cluster_embeddings.npy   (num_clusters, 384) float32, L2-normalized
                            - one centroid per cluster, used for semantic
                              search (cosine similarity == dot product here)
  clusters.parquet         one row per cluster: cluster_id, representative,
                            size, total_count - row order matches
                            cluster_embeddings.npy
  cluster_year.parquet     long form: cluster_id, year, count
  cluster_country.parquet  long form: cluster_id, country, count
                            (country aliases summed - see countries.py)
  keyword_lookup.json      flat [[member_keyword, cluster_row_index], ...]
                            for lexical fuzzy matching

Centroids are computed from the actual member keyword embeddings. The old
stage1_labels cache belongs to a historical per-year run and must not be
mixed into the current tree.

Usage:
    python 05_webapp/build_index.py [--threshold 0.75] [--clusters-file PATH]
    python 05_webapp/prepare_indices.py  # all heights plus keyword statistics
"""

import os
import sys
import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from countries import country_counts

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLUSTERING_DIR = os.path.join(ROOT, "04_clustering")
EMBEDDINGS_DIR = os.path.join(CLUSTERING_DIR, "precomputed_embeddings")
OUT_DIR = os.path.join(HERE, "index")

def load_leaf_embeddings():
    keywords_path = os.path.join(EMBEDDINGS_DIR, "leaf_keywords_keywords.json")
    embeddings_path = os.path.join(EMBEDDINGS_DIR, "leaf_keywords_embeddings.npy")
    if not (os.path.exists(keywords_path) and os.path.exists(embeddings_path)):
        raise SystemExit(
            f"Missing leaf embeddings under {EMBEDDINGS_DIR} - run "
            "04_clustering/cluster_keywords.py first."
        )
    keywords = json.loads(Path(keywords_path).read_text(encoding='utf-8'))
    embeddings = np.load(embeddings_path)
    if len(keywords) != embeddings.shape[0]:
        raise SystemExit(
            f"leaf_keywords_keywords.json has {len(keywords)} entries but "
            f"leaf_keywords_embeddings.npy has {embeddings.shape[0]} rows - "
            "these are out of sync, re-run the clustering step."
        )
    lookup = {kw: i for i, kw in enumerate(keywords)}
    return lookup, embeddings


def build(threshold: float, clusters_file: str, out_dir=None):
    out_dir = out_dir or os.path.join(OUT_DIR, f'dt{threshold:g}')
    print(f"[1/4] Loading clusters from {clusters_file} ...")
    data = json.loads(Path(clusters_file).read_text(encoding='utf-8'))
    clusters = data["clusters"]
    if data.get('meta', {}).get('threshold', threshold) != threshold:
        raise ValueError('Requested threshold does not match cluster metadata')
    print(f"      {len(clusters)} clusters, meta={data.get('meta')}")

    print("[2/4] Loading leaf keyword embeddings ...")
    leaf_lookup, leaf_embeddings = load_leaf_embeddings()

    print("[3/4] Computing per-cluster centroids + flattening tables ...")
    cluster_rows = []
    year_rows = []
    country_rows = []
    keyword_lookup = []
    members = {}
    centroids = np.zeros((len(clusters), leaf_embeddings.shape[1]), dtype=np.float32)

    for row_idx, (cluster_id, c) in enumerate(sorted(
        clusters.items(), key=lambda kv: int(kv[0].split("_")[1])
    )):
        member_vecs = []
        members[str(row_idx)] = c.get('member_keywords', [])
        for kw in c.get("member_keywords", []):
            keyword_lookup.append([kw, row_idx])
            idx = leaf_lookup.get(kw)
            if idx is not None:
                member_vecs.append(leaf_embeddings[idx])
            else:
                raise ValueError(f'Missing embedding for {kw!r}; rebuild the keyword cache')
        # the representative itself is also a valid, often-typed search term
        keyword_lookup.append([c["representative"], row_idx])

        if not member_vecs or len(member_vecs) != c['size']:
            raise ValueError(f'{cluster_id} has inconsistent member count')
        centroid = np.mean(member_vecs, axis=0)

        norm = np.linalg.norm(centroid)
        if not np.isfinite(norm) or norm <= 0:
            raise ValueError(f'{cluster_id} has no valid semantic centroid')
        centroids[row_idx] = centroid / norm

        cluster_rows.append({
            "cluster_id": cluster_id,
            "row_idx": row_idx,
            "representative": c["representative"],
            "size": c["size"],
            "total_count": c["total_count"],
        })
        for year, count in c.get("years", {}).items():
            year_rows.append({"cluster_id": cluster_id, "row_idx": row_idx,
                               "year": int(year), "count": count})
        for norm_country, count in country_counts(c.get("countries", {})).items():
            country_rows.append({"cluster_id": cluster_id, "row_idx": row_idx,
                                  "country": norm_country, "count": count})

    print("[4/4] Writing artifacts to", out_dir)
    os.makedirs(out_dir, exist_ok=True)
    np.save(os.path.join(out_dir, "cluster_embeddings.npy"), centroids)
    pd.DataFrame(cluster_rows).to_parquet(os.path.join(out_dir, "clusters.parquet"))
    pd.DataFrame(year_rows, columns=['cluster_id','row_idx','year','count']).to_parquet(os.path.join(out_dir, "cluster_year.parquet"))
    pd.DataFrame(country_rows, columns=['cluster_id','row_idx','country','count']).to_parquet(os.path.join(out_dir, "cluster_country.parquet"))
    Path(out_dir, 'keyword_lookup.json').write_text(json.dumps(keyword_lookup), encoding='utf-8')
    Path(out_dir, 'members.json').write_text(json.dumps(members), encoding='utf-8')
    Path(out_dir, 'meta.json').write_text(json.dumps({"threshold": threshold, "source_file": os.path.basename(clusters_file),
                "num_clusters": len(clusters), "num_keywords": data['meta']['num_keywords'],
                "aggregate_sha256": data['meta'].get('aggregate_sha256')}, indent=2), encoding='utf-8')

    print(f"\nDone. {len(cluster_rows)} clusters, {len(year_rows)} year rows, "
          f"{len(country_rows)} country rows, {len(keyword_lookup)} lexical entries.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=1.0,
                         help="Which dendrogram cut to index (default 1.0)")
    parser.add_argument("--clusters-file", default=None,
                         help="Override the input file path directly")
    args = parser.parse_args()

    clusters_file = args.clusters_file or os.path.join(
        CLUSTERING_DIR, "explorer_results", f"clusters_dt{args.threshold}.json"
    )
    build(args.threshold, clusters_file)

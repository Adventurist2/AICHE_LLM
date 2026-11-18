#!/usr/bin/env python3
"""
Quality analysis on top of compare_clustering_algorithms.py's saved results.

Two checks, deliberately kept separate because they can disagree:

1. Silhouette score - a purely geometric tightness measure. Included as a
   supplementary data point, NOT as the final word: PROJECT_REPORT.md
   section 10 already documents how silhouette score misled the source
   methodology's UMAP evaluation (rewarding geometric tightness that didn't
   correspond to semantic coherence). It's included here for the same
   reason - to check whether it's misleading again, not because it's
   trusted by default.

2. Manual coherence sampling - a fixed-seed random sample of mid-size
   clusters per algorithm (NOT the top-N largest, which would cherry-pick
   the easiest cases), read and judged for topic drift.

Run compare_clustering_algorithms.py first to generate the *_result.json
files this script reads.

Usage:
    python 04_clustering/analyze_cluster_quality.py
"""

import json
import random
from collections import Counter

import numpy as np
from sklearn.metrics import silhouette_score

TEST_FIXTURE = "04_clustering/aggregate_test_2016.json"
EMBED_CACHE_KEYWORDS = "04_clustering/precomputed_embeddings/leaf_keywords_keywords.json"
EMBED_CACHE_VECTORS = "04_clustering/precomputed_embeddings/leaf_keywords_embeddings.npy"
RESULT_DIR = "04_clustering/algorithm_comparison"
ALGORITHMS = ["ward", "hdbscan", "kmeans"]
SAMPLE_SEED = 11
SAMPLE_SIZE = 6
MIN_SAMPLE_CLUSTER_SIZE = 3  # skip singletons/pairs - too easy to look "coherent" trivially


def load_embeddings():
    keywords_cache = json.load(open(EMBED_CACHE_KEYWORDS, encoding="utf-8"))
    embeddings_cache = np.load(EMBED_CACHE_VECTORS)
    idx = {k: i for i, k in enumerate(keywords_cache)}

    test_kws = sorted(json.load(open(TEST_FIXTURE, encoding="utf-8")).keys())
    X = np.array([embeddings_cache[idx[k]] for k in test_kws], dtype=np.float64)
    return test_kws, X


def compute_silhouette(name, test_kws, X):
    kw_to_row = {kw: i for i, kw in enumerate(test_kws)}
    result = json.load(open(f"{RESULT_DIR}/{name}_result.json", encoding="utf-8"))

    labels = np.full(len(test_kws), -1, dtype=int)
    for cid, members in result["clusters"].items():
        for kw in members:
            labels[kw_to_row[kw]] = int(cid)

    # Silhouette is undefined for noise points and singleton clusters - drop both,
    # same treatment applied uniformly across all three algorithms for a fair comparison.
    counts = Counter(labels[labels != -1])
    valid = (labels != -1) & np.isin(labels, [c for c, n in counts.items() if n >= 2])

    score = silhouette_score(X[valid], labels[valid], metric="cosine") if valid.sum() > 0 else None
    return {
        "algorithm": name,
        "num_clusters": result["num_clusters"],
        "num_noise": result["num_noise"],
        "silhouette_cosine": round(score, 4) if score is not None else None,
        "n_points_scored": int(valid.sum()),
    }


def sample_clusters(name, seed=SAMPLE_SEED, k=SAMPLE_SIZE):
    result = json.load(open(f"{RESULT_DIR}/{name}_result.json", encoding="utf-8"))
    eligible = {cid: m for cid, m in result["clusters"].items() if len(m) >= MIN_SAMPLE_CLUSTER_SIZE}
    random.seed(seed)
    chosen = random.sample(list(eligible.items()), min(k, len(eligible)))
    return chosen


def main():
    test_kws, X = load_embeddings()

    print("=" * 70)
    print("SILHOUETTE SCORE (cosine, non-singleton/non-noise clusters only)")
    print("Supplementary metric only - see module docstring for why it is")
    print("NOT treated as the deciding factor.")
    print("=" * 70)
    sil_results = []
    for name in ALGORITHMS:
        r = compute_silhouette(name, test_kws, X)
        sil_results.append(r)
        print(f"  {name:10s} clusters={r['num_clusters']:5d}  noise={r['num_noise']:4d}  "
              f"silhouette={r['silhouette_cosine']}  (scored on {r['n_points_scored']} points)")

    with open(f"{RESULT_DIR}/silhouette_scores.json", "w", encoding="utf-8") as f:
        json.dump(sil_results, f, indent=2)

    print()
    print("=" * 70)
    print(f"MANUAL COHERENCE SAMPLE ({SAMPLE_SIZE} random mid-size clusters per algorithm,")
    print(f"seed={SAMPLE_SEED} - NOT the top-N largest, to avoid cherry-picking easy cases)")
    print("=" * 70)
    # Cluster text can contain unicode punctuation (e.g. non-breaking hyphens)
    # that Windows' cp1252 console can't display - write straight to the file
    # (utf-8) and only print ASCII-safe progress to the console.
    sample_lines = []
    for name in ALGORITHMS:
        sample_lines.append(f"=== {name.upper()} ===")
        clusters = sample_clusters(name)
        print(f"\n{name.upper()}: sampled {len(clusters)} clusters (sizes: {[len(m) for _, m in clusters]})")
        for cid, members in clusters:
            sample_lines.append(f"  [{len(members)}] {members}")
        sample_lines.append("")

    with open(f"{RESULT_DIR}/manual_coherence_sample.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(sample_lines))

    print(f"\nWritten: {RESULT_DIR}/silhouette_scores.json, {RESULT_DIR}/manual_coherence_sample.txt")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Keyword Clustering Algorithm
- Loads JSON with keyword keys (like the sample data)
- Builds vector embeddings using character n-gram TF-IDF (no external API)
- Clusters keywords using K-Means
- Selects a canonical word per cluster (the centroid-nearest keyword)
- Outputs a JSON with cluster assignments + embeddings summary
"""

import json
import math
import random
import argparse
import sys
from collections import defaultdict


# ─────────────────────────────────────────────
# 1. TEXT PREPROCESSING
# ─────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    """Lowercase and split on whitespace/punctuation."""
    import re
    return re.findall(r'[a-z]+', text.lower())


def char_ngrams(text: str, n: int = 3) -> list[str]:
    """Extract character n-grams from a string."""
    padded = f"_{text}_"
    return [padded[i:i+n] for i in range(len(padded) - n + 1)]


def get_features(keyword: str) -> list[str]:
    """
    Combine word unigrams + bigrams + character trigrams as features.
    This gives semantic + morphological signal without any external model.
    """
    words = tokenize(keyword)
    unigrams = words
    bigrams = [f"{words[i]}_{words[i+1]}" for i in range(len(words)-1)]
    char3 = char_ngrams(keyword.lower())
    return unigrams + bigrams + char3


# ─────────────────────────────────────────────
# 2. TF-IDF VECTORIZATION
# ─────────────────────────────────────────────

def build_tfidf_vectors(keywords: list[str]) -> tuple[list[dict], list[str]]:
    """
    Build TF-IDF sparse vectors for each keyword.
    Returns (list_of_sparse_vectors, vocabulary_list)
    """
    # Build corpus of feature bags
    corpus = [get_features(kw) for kw in keywords]

    # Compute document frequency
    df = defaultdict(int)
    for features in corpus:
        for feat in set(features):
            df[feat] += 1

    N = len(keywords)
    vocabulary = sorted(df.keys())
    vocab_index = {f: i for i, f in enumerate(vocabulary)}

    # Build TF-IDF vectors (sparse as dicts)
    vectors = []
    for features in corpus:
        tf = defaultdict(float)
        for feat in features:
            tf[feat] += 1.0
        # Normalize TF
        total = sum(tf.values())
        vec = {}
        for feat, count in tf.items():
            tfidf = (count / total) * math.log((N + 1) / (df[feat] + 1))
            if tfidf != 0:
                vec[vocab_index[feat]] = tfidf
        vectors.append(vec)

    return vectors, vocabulary


def l2_normalize(vec: dict) -> dict:
    norm = math.sqrt(sum(v*v for v in vec.values()))
    if norm == 0:
        return vec
    return {k: v/norm for k, v in vec.items()}


def cosine_similarity(a: dict, b: dict) -> float:
    """Dot product of two normalized sparse vectors."""
    dot = 0.0
    for k, v in a.items():
        if k in b:
            dot += v * b[k]
    return dot


def euclidean_distance(a: dict, b: dict) -> float:
    """Euclidean distance between two sparse vectors."""
    keys = set(a) | set(b)
    return math.sqrt(sum((a.get(k, 0) - b.get(k, 0))**2 for k in keys))


# ─────────────────────────────────────────────
# 3. K-MEANS CLUSTERING
# ─────────────────────────────────────────────

def sparse_mean(vecs: list[dict]) -> dict:
    """Compute mean of a list of sparse vectors."""
    if not vecs:
        return {}
    result = defaultdict(float)
    for v in vecs:
        for k, val in v.items():
            result[k] += val
    n = len(vecs)
    return {k: v/n for k, v in result.items()}


def kmeans(vectors: list[dict], k: int, max_iter: int = 100, seed: int = 42) -> list[int]:
    """
    K-Means on sparse TF-IDF vectors using cosine distance.
    Returns cluster assignments (list of ints, one per keyword).
    """
    random.seed(seed)
    n = len(vectors)

    if k >= n:
        return list(range(n))

    # K-Means++ initialization
    centroids = []
    centroids.append(l2_normalize(vectors[random.randint(0, n-1)]))

    for _ in range(k - 1):
        distances = []
        for vec in vectors:
            nv = l2_normalize(vec)
            min_dist = min(euclidean_distance(nv, c) for c in centroids)
            distances.append(min_dist ** 2)
        total = sum(distances)
        probs = [d/total for d in distances]
        # Weighted random pick
        r = random.random()
        cumulative = 0
        chosen = n - 1
        for idx, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                chosen = idx
                break
        centroids.append(l2_normalize(vectors[chosen]))

    assignments = [0] * n

    for iteration in range(max_iter):
        # Assignment step
        new_assignments = []
        for vec in vectors:
            nv = l2_normalize(vec)
            sims = [cosine_similarity(nv, c) for c in centroids]
            new_assignments.append(sims.index(max(sims)))

        # Check convergence
        if new_assignments == assignments and iteration > 0:
            print(f"  Converged at iteration {iteration}")
            break
        assignments = new_assignments

        # Update step
        new_centroids = []
        for ci in range(k):
            cluster_vecs = [l2_normalize(vectors[i]) for i, a in enumerate(assignments) if a == ci]
            if cluster_vecs:
                centroid = l2_normalize(sparse_mean(cluster_vecs))
            else:
                # Re-initialize dead centroid
                centroid = l2_normalize(vectors[random.randint(0, n-1)])
            new_centroids.append(centroid)
        centroids = new_centroids

    return assignments, centroids


# ─────────────────────────────────────────────
# 4. CANONICAL WORD SELECTION
# ─────────────────────────────────────────────

def pick_canonical(keywords: list[str], vectors: list[dict], centroid: dict) -> str:
    """
    The canonical word is the keyword whose normalized vector is
    closest (highest cosine similarity) to the cluster centroid.
    """
    best_kw = keywords[0]
    best_sim = -1.0
    for kw, vec in zip(keywords, vectors):
        sim = cosine_similarity(l2_normalize(vec), centroid)
        if sim > best_sim:
            best_sim = sim
            best_kw = kw
    return best_kw


# ─────────────────────────────────────────────
# 5. MAIN PIPELINE
# ─────────────────────────────────────────────

def cluster_keywords(input_path: str, k: int, output_path: str):
    print(f"\n{'='*55}")
    print(f"  Keyword Clustering  |  k={k}  |  Input: {input_path}")
    print(f"{'='*55}")

    # Load data
    with open(input_path, 'r',encoding='utf-8') as f:
        data = json.load(f)

    keywords = list(data.keys())
    print(f"\n[1] Loaded {len(keywords)} keywords from JSON")

    if len(keywords) < k:
        print(f"  WARNING: k={k} > number of keywords ({len(keywords)}). Setting k={len(keywords)}")
        k = len(keywords)

    # Build TF-IDF vectors
    print(f"[2] Building TF-IDF embeddings (word n-grams + char trigrams)...")
    vectors, vocabulary = build_tfidf_vectors(keywords)
    print(f"    Vocabulary size: {len(vocabulary)} features")

    # Cluster
    print(f"[3] Running K-Means (k={k}, cosine distance)...")
    assignments, centroids = kmeans(vectors, k)

    # Build output
    print(f"[4] Selecting canonical words per cluster...")
    clusters = defaultdict(list)
    for idx, cluster_id in enumerate(assignments):
        clusters[cluster_id].append(idx)

    output = {
        "meta": {
            "total_keywords": len(keywords),
            "num_clusters": k,
            "vocab_size": len(vocabulary),
            "embedding_type": "TF-IDF (word unigrams + bigrams + char-3grams)"
        },
        "clusters": {}
    }

    for cluster_id, indices in sorted(clusters.items()):
        cluster_keywords_list = [keywords[i] for i in indices]
        cluster_vecs = [vectors[i] for i in indices]
        canonical = pick_canonical(cluster_keywords_list, cluster_vecs, centroids[cluster_id])

        # Store embedding as sorted sparse list for readability
        cluster_members = []
        for kw, vec in zip(cluster_keywords_list, cluster_vecs):
            nv = l2_normalize(vec)
            sim_to_centroid = cosine_similarity(nv, centroids[cluster_id])
            # Top 10 features by weight for inspection
            top_features = sorted(nv.items(), key=lambda x: -x[1])[:10]
            top_feature_names = [(vocabulary[fi], round(fw, 4)) for fi, fw in top_features]
            cluster_members.append({
                "keyword": kw,
                "sim_to_centroid": round(sim_to_centroid, 4),
                "top_embedding_features": top_feature_names,
                "metadata": {
                    "total_count": data[kw].get("total_count"),
                    "years": data[kw].get("years"),
                    "countries": data[kw].get("countries")
                }
            })

        # Sort members by similarity to centroid (most representative first)
        cluster_members.sort(key=lambda x: -x["sim_to_centroid"])

        output["clusters"][f"cluster_{cluster_id}"] = {
            "canonical_word": canonical,
            "size": len(cluster_keywords_list),
            "members": cluster_members
        }

        print(f"    Cluster {cluster_id:2d}: canonical='{canonical}' | members={len(cluster_keywords_list)}")

    # Save
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n[5] Output saved to: {output_path}")
    print(f"{'='*55}\n")
    return output


# ─────────────────────────────────────────────
# 6. CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cluster JSON keywords using TF-IDF embeddings + K-Means"
    )
    parser.add_argument("input", help="Path to input JSON file")
    parser.add_argument("k", type=int, help="Number of clusters")
    parser.add_argument("--output", default="clusters_output.json", help="Output JSON path")
    args = parser.parse_args()

    result = cluster_keywords(args.input, args.k, args.output)
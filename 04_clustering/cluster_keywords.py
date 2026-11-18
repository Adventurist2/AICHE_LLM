#!/usr/bin/env python3
"""
Semantic clustering of aggregate.json's keywords.

Method (from the MRS keyword-trend-analyser paper): embed keywords with a
sentence-transformer and cluster directly on the full-dimensional embeddings
with Ward-linkage agglomerative clustering. No UMAP/PCA - the paper found
dimensionality reduction improves silhouette score while making cluster
coherence measurably worse on manual inspection.

Single-pass design: all keywords from all years are clustered together in
one Ward-linkage pass. The paper split this per-year to survive a 37 GB
pairwise-distance matrix, but fastcluster's linkage_vector is O(n) memory
(~160 MB at 104k keywords), so that constraint does not apply here. Doing it
in one pass also means each keyword lands in exactly one cluster - the
per-year variant assigned ~8% of keywords to two different clusters, since
the same keyword could group differently depending on which year it was
clustered with.

Cutting the same dendrogram at several distance thresholds yields several
granularities (fine/moderate/broad) for the cost of one clustering run.

Cluster labels come from a LOCAL Ollama model (default llama3.2, same model
keyword_grouping_2.ipynb uses), batched several clusters per request. Local
inference has no rate limit - the earlier Groq-based version spent hours
stalled on 429s. Requires `ollama serve` running with the model pulled.
--no-llm skips labeling entirely and uses the free centroid-nearest member.

Embeddings are cached in precomputed_embeddings/ - re-running after adding
new keywords only embeds the new ones. Labeling is checkpointed per batch,
so an interrupted run resumes without repeating work.

Usage:
    python 04_clustering/cluster_keywords.py [02_extraction/aggregate.json] [--no-llm] [--force]
    python 04_clustering/cluster_keywords.py --label-model mistral    # any pulled model
"""

import os
import sys
import json
import time
import logging
import hashlib
from collections import defaultdict

import numpy as np
from scipy.cluster.hierarchy import fcluster

try:
    import fastcluster
except ImportError:
    raise SystemExit("Missing dependency: pip install fastcluster")

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise SystemExit("Missing dependency: pip install sentence-transformers")

try:
    import ollama
except ImportError:
    raise SystemExit("Missing dependency: pip install ollama")


# ── Config ───────────────────────────────────────────────────────────────────

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
THRESHOLDS = [0.25, 0.4, 0.5, 0.6, 0.75, 0.9, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
MIN_KEYWORDS_TO_CLUSTER = 2
CLUSTERS_PER_LLM_CALL = 10   # smaller than an API batch: local models hold structured output better over fewer items
MAX_MEMBERS_IN_PROMPT = 25
CACHE_DIR = "04_clustering/precomputed_embeddings"
OUTPUT_DIR = "04_clustering/explorer_results"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("04_clustering/clustering.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


# ── IO helpers ───────────────────────────────────────────────────────────────

def atomic_write_json(path: str, obj, indent=None) -> None:
    """Write via a temp file + rename so a crash mid-write can't leave a
    corrupt/partial checkpoint that a resumed run would then try to load."""
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
    os.replace(tmp_path, path)


def load_aggregate(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Embedding cache (incremental) ───────────────────────────────────────────

class EmbeddingCache:
    """Persists {text: embedding} to disk; only embeds text not seen before."""

    def __init__(self, name: str, model: SentenceTransformer):
        self.model = model
        self.keywords_path = os.path.join(CACHE_DIR, f"{name}_keywords.json")
        self.embeddings_path = os.path.join(CACHE_DIR, f"{name}_embeddings.npy")
        os.makedirs(CACHE_DIR, exist_ok=True)

        if os.path.exists(self.keywords_path) and os.path.exists(self.embeddings_path):
            with open(self.keywords_path, "r", encoding="utf-8") as f:
                self._keywords = json.load(f)
            self._embeddings = np.load(self.embeddings_path)
        else:
            self._keywords = []
            self._embeddings = np.zeros((0, self.model.get_sentence_embedding_dimension()), dtype=np.float32)

        self._index = {k: i for i, k in enumerate(self._keywords)}

    def get(self, texts: list) -> np.ndarray:
        missing = [t for t in texts if t not in self._index]
        if missing:
            logger.info(f"Embedding {len(missing)} new / {len(texts)} requested (cache: {len(self._keywords)})")
            new_vecs = self.model.encode(missing, batch_size=256, show_progress_bar=True)
            start = len(self._keywords)
            self._keywords.extend(missing)
            for i, t in enumerate(missing):
                self._index[t] = start + i
            self._embeddings = np.vstack([self._embeddings, new_vecs]) if len(self._embeddings) else np.array(new_vecs)
            self._save()

        idx = [self._index[t] for t in texts]
        return self._embeddings[idx]

    def _save(self):
        tmp_npy = f"{self.embeddings_path}.tmp.npy"
        np.save(tmp_npy, self._embeddings)
        os.replace(tmp_npy, self.embeddings_path)

        tmp_json = f"{self.keywords_path}.tmp"
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(self._keywords, f, ensure_ascii=False)
        os.replace(tmp_json, self.keywords_path)


# ── Cluster labeling via local Ollama (batched) ─────────────────────────────

LABEL_SYSTEM_PROMPT = """
You are an expert in chemical engineering. You will be given several numbered
clusters of related chemical-engineering research keywords. For EACH cluster,
choose one concise, specific phrase (2-5 words) that summarizes that whole
cluster - prefer specific technical terms over broad ones.

Respond with ONLY a JSON object mapping each cluster number to its label:
{"1": "label one", "2": "label two", ...}
Include every cluster number you were given. No other text.
""".strip()


class LabelEngine:
    """Labels clusters with a local Ollama model - no API keys, no rate limits."""

    def __init__(self, model: str):
        self.model = model
        try:
            available = [m["model"] for m in ollama.list()["models"]]
        except Exception as e:
            raise SystemExit(
                f"Cannot reach the Ollama server ({e}).\n"
                "Start it with `ollama serve`, or pass --no-llm to skip labeling."
            )
        if model not in available and f"{model}:latest" not in available:
            raise SystemExit(
                f"Ollama model {model!r} is not pulled. Available: {', '.join(available) or '(none)'}\n"
                f"Pull it with `ollama pull {model}`, or pass --label-model with one of the above."
            )

    def label_batch(self, batch: list) -> dict:
        """batch: [(cluster_id, [members...])] -> {cluster_id: label}.
        Any cluster the model skips or mangles keeps its centroid representative."""
        lines = []
        for n, (_, members) in enumerate(batch, start=1):
            shown = ", ".join(members[:MAX_MEMBERS_IN_PROMPT])
            lines.append(f"Cluster {n}: {shown}")

        try:
            resp = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": LABEL_SYSTEM_PROMPT},
                    {"role": "user", "content": "\n".join(lines) + "\n\nJSON:"},
                ],
                format="json",           # constrains decoding to valid JSON
                options={"temperature": 0.0},
            )
            raw = resp["message"]["content"]
        except Exception as e:
            logger.error(f"Ollama call failed: {e} - keeping centroid labels for this batch")
            return {}

        try:
            start, end = raw.find("{"), raw.rfind("}")
            parsed = json.loads(raw[start:end + 1]) if start != -1 and end != -1 else {}
        except (json.JSONDecodeError, ValueError):
            logger.warning("Unparseable batch response - keeping centroid labels")
            return {}

        out = {}
        for n, (cid, _) in enumerate(batch, start=1):
            label = parsed.get(str(n))
            if isinstance(label, str) and label.strip() and label.strip().lower() != "none":
                out[cid] = label.strip().strip('"')
        return out


# ── Clustering ───────────────────────────────────────────────────────────────

def build_linkage(embeddings: np.ndarray):
    """Ward-linkage dendrogram over the full-dimensional embeddings.
    Built once and cut at every threshold - the tree does not depend on
    where you cut it, so recomputing it per threshold is pure waste."""
    if embeddings.shape[0] < MIN_KEYWORDS_TO_CLUSTER:
        return None
    return fastcluster.linkage_vector(embeddings, method="ward")


def cut_dendrogram(linkage_matrix, n: int, threshold: float) -> np.ndarray:
    """Returns a 1-indexed cluster label per keyword."""
    if linkage_matrix is None:
        return np.arange(1, n + 1)
    return fcluster(linkage_matrix, t=threshold, criterion="distance")


def centroid_representative(members: list, member_embeddings: np.ndarray) -> str:
    """Free representative: member closest (cosine) to the cluster's mean embedding."""
    norms = member_embeddings / np.linalg.norm(member_embeddings, axis=1, keepdims=True)
    centroid = norms.mean(axis=0)
    centroid = centroid / np.linalg.norm(centroid)
    return members[int(np.argmax(norms @ centroid))]


def group_clusters(keywords: list, embeddings: np.ndarray, labels: np.ndarray, aggregate: dict) -> dict:
    """cluster_id -> {representative, members}. Members are sorted by mention
    count so the most prominent keywords lead the LLM prompt."""
    groups = defaultdict(list)
    for i, (kw, cid) in enumerate(zip(keywords, labels)):
        groups[int(cid)].append((kw, i))

    result = {}
    for cid, pairs in groups.items():
        pairs.sort(key=lambda p: -aggregate[p[0]]["total_count"])
        members = [kw for kw, _ in pairs]
        idx = [i for _, i in pairs]
        rep = members[0] if len(members) == 1 else centroid_representative(members, embeddings[idx])
        result[cid] = {"representative": rep, "members": members}
    return result


def apply_llm_labels(clusters: dict, engine: LabelEngine, ckpt_path: str, force=False) -> None:
    """Relabel multi-member clusters in place, checkpointing after each batch."""
    done = {}
    if os.path.exists(ckpt_path) and not force:
        with open(ckpt_path, "r", encoding="utf-8") as f:
            done = json.load(f)
        logger.info(f"Resuming labeling: {len(done)} clusters already labeled")

    pending = [(cid, info["members"]) for cid, info in clusters.items()
               if len(info["members"]) > 1 and str(cid) not in done]

    total_batches = (len(pending) + CLUSTERS_PER_LLM_CALL - 1) // CLUSTERS_PER_LLM_CALL
    logger.info(f"Labeling {len(pending)} clusters in {total_batches} batched calls")

    for b in range(0, len(pending), CLUSTERS_PER_LLM_CALL):
        batch = pending[b:b + CLUSTERS_PER_LLM_CALL]
        for cid, label in engine.label_batch(batch).items():
            done[str(cid)] = label
        atomic_write_json(ckpt_path, done)

        batch_num = b // CLUSTERS_PER_LLM_CALL + 1
        if batch_num % 10 == 0 or batch_num == total_batches:
            logger.info(f"  batch {batch_num}/{total_batches} ({len(done)} labeled)")

    for cid, info in clusters.items():
        if str(cid) in done:
            info["representative"] = done[str(cid)]


# ── Roll-up ──────────────────────────────────────────────────────────────────

def rollup_cluster_stats(aggregate: dict, members: list) -> dict:
    total_count = 0
    years_count = defaultdict(int)
    countries_count = defaultdict(int)
    authors_count = defaultdict(int)

    for kw in members:
        rec = aggregate.get(kw)
        if not rec:
            continue
        total_count += rec["total_count"]
        for year, c in rec.get("years", {}).items():
            years_count[year] += c
        for country, c in rec.get("countries", {}).items():
            countries_count[country] += c
        for author, c in rec.get("authors", {}).items():
            authors_count[author] += c

    return {
        "size": len(members),
        "member_keywords": members,
        "total_count": total_count,
        "years": dict(sorted(years_count.items())),
        "countries": dict(sorted(countries_count.items(), key=lambda x: -x[1])),
        "authors": dict(sorted(authors_count.items(), key=lambda x: -x[1])),
    }


def main():
    global OUTPUT_DIR
    import argparse
    parser = argparse.ArgumentParser(description="Semantic clustering of aggregate.json's keywords")
    parser.add_argument("aggregate_path", nargs="?", default="02_extraction/aggregate.json")
    parser.add_argument("--no-llm", action="store_true",
                        help="Skip LLM labeling; use the free centroid-nearest member as each label")
    parser.add_argument("--label-model", default="llama3.2",
                        help="Local Ollama model for cluster labeling (default: llama3.2)")
    parser.add_argument("--force", action="store_true", help="Ignore existing checkpoints and recompute")
    parser.add_argument("--output-dir", default=OUTPUT_DIR,
                        help="Checkpoint/output directory. Use a distinct one for subset/test runs.")
    parser.add_argument('--thresholds', nargs='+', type=float, default=THRESHOLDS,
                        help='Dendrogram cut heights (default: %(default)s)')
    parser.add_argument('--reuse-labels', default=None,
                        help='Reuse labels only for exactly matching member sets from this directory')
    parsed = parser.parse_args()

    OUTPUT_DIR = parsed.output_dir
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    aggregate = load_aggregate(parsed.aggregate_path)
    keywords = sorted(aggregate.keys())
    fingerprint = hashlib.sha256(json.dumps(aggregate, sort_keys=True).encode()).hexdigest()
    if not parsed.thresholds or any(not np.isfinite(t) or t <= 0 for t in parsed.thresholds):
        parser.error('Thresholds must be finite positive numbers')
    logger.info(f"Loaded {len(keywords)} unique keywords from {parsed.aggregate_path}")

    embedder = SentenceTransformer(EMBED_MODEL_NAME)
    embeddings = EmbeddingCache("leaf_keywords", embedder).get(keywords)

    engine = None if parsed.no_llm else LabelEngine(parsed.label_model)

    pending = []
    for t in sorted(set(parsed.thresholds)):
        path = os.path.join(OUTPUT_DIR, f'clusters_dt{t}.json')
        try:
            meta = load_aggregate(path)['meta']
            valid = meta.get('aggregate_sha256') == fingerprint
        except (OSError, ValueError, KeyError):
            valid = False
        if parsed.force or not valid:
            pending.append(t)
    if not pending:
        logger.info("All thresholds already written; nothing to do (use --force to recompute)")
        return

    logger.info(f"Building Ward dendrogram over {len(keywords)} keywords "
                f"({embeddings.shape[1]}-dim, no dimensionality reduction)")
    t0 = time.time()
    tree_path = os.path.join(OUTPUT_DIR, 'ward_tree.npy')
    tree_meta = os.path.join(OUTPUT_DIR, 'ward_tree_meta.json')
    try:
        saved_meta = load_aggregate(tree_meta)
        reuse_tree = (saved_meta.get('aggregate_sha256') == fingerprint
                      and saved_meta.get('embedding_model') == EMBED_MODEL_NAME)
    except (OSError, ValueError):
        reuse_tree = False
    if reuse_tree and os.path.exists(tree_path):
        linkage_matrix = np.load(tree_path)
    else:
        linkage_matrix = build_linkage(embeddings)
        if linkage_matrix is not None:
            np.save(tree_path + '.tmp.npy', linkage_matrix)
            os.replace(tree_path + '.tmp.npy', tree_path)
            atomic_write_json(tree_meta, {'aggregate_sha256': fingerprint,
                                         'embedding_model': EMBED_MODEL_NAME})
    known_labels = {}
    if parsed.reuse_labels:
        import glob
        for path in glob.glob(os.path.join(parsed.reuse_labels, 'clusters_dt*.json')):
            try:
                for info in load_aggregate(path)['clusters'].values():
                    known_labels[tuple(sorted(info['member_keywords']))] = info['representative']
            except (OSError, ValueError, KeyError):
                logger.warning('Skipping unreadable labels: %s', path)
    logger.info(f"Dendrogram built in {time.time() - t0:.1f}s - cutting at {pending}")

    for threshold in pending:
        out_path = os.path.join(OUTPUT_DIR, f"clusters_dt{threshold}.json")

        labels = cut_dendrogram(linkage_matrix, len(keywords), threshold)
        clusters = group_clusters(keywords, embeddings, labels, aggregate)
        for info in clusters.values():
            info['representative'] = known_labels.get(tuple(sorted(info['members'])), info['representative'])
        logger.info(f"Threshold {threshold}: {len(clusters)} clusters")

        if engine is not None:
            model_key = hashlib.sha256(parsed.label_model.encode()).hexdigest()[:8]
            apply_llm_labels(clusters, engine,
                             os.path.join(OUTPUT_DIR, f"labels_{fingerprint[:12]}_{model_key}_dt{threshold}.json"),
                             force=parsed.force)

        output = {
            "meta": {
                "embedding_model": EMBED_MODEL_NAME,
                "threshold": threshold,
                "num_clusters": len(clusters),
                "num_keywords": len(keywords),
                'aggregate_sha256': fingerprint,
                "labeling": "centroid" if engine is None else parsed.label_model,
            },
            "clusters": {
                f"cluster_{cid}": {
                    "representative": info["representative"],
                    **rollup_cluster_stats(aggregate, info["members"]),
                }
                for cid, info in sorted(clusters.items())
            },
        }
        atomic_write_json(out_path, output, indent=2)
        logger.info(f"Wrote {out_path} ({len(clusters)} clusters)")

    logger.info("Done.")


if __name__ == "__main__":
    main()

"""
Hybrid (lexical + semantic) search over clustered keywords.

Two independent signals, fused with Reciprocal Rank Fusion (RRF) so neither
has to be rescaled to match the other's range:

  - lexical:  RapidFuzz fuzzy match against every raw member keyword and
              cluster representative (index/keyword_lookup.json). Robust to
              typos and partial words ("catalisys" -> "catalysis").
  - semantic: cosine similarity between the query's own sentence-transformer
              embedding and every cluster centroid (index/cluster_embeddings.npy).
              Robust to synonyms/rewording ("battery" -> "energy storage")
              that share no substring with the query.

Load once (IndexBundle.load), call search() per query - both steps are a
handful of milliseconds at this data size (~30k clusters), no vector DB or
ANN index needed.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any

import numpy as np
import pandas as pd
from rapidfuzz import process, fuzz
from countries import country_counts

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.environ.get('AICHE_INDEX_DIR') or os.path.join(HERE, "index")

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"  # must match 04_clustering/cluster_keywords.py


@dataclass
class IndexBundle:
    clusters: pd.DataFrame          # cluster_id, row_idx, representative, size, total_count
    cluster_year: pd.DataFrame      # cluster_id, row_idx, year, count
    cluster_country: pd.DataFrame   # cluster_id, row_idx, country, count
    embeddings: np.ndarray          # (num_clusters, dim), L2-normalized
    keyword_lookup: List[List[Any]] # [[keyword_text, row_idx], ...]
    model: Any                      # SentenceTransformer, lazily attached
    members: Any = None

    @classmethod
    def load(cls, index_dir: str = INDEX_DIR, model=None):
        clusters = pd.read_parquet(os.path.join(index_dir, "clusters.parquet"))
        cluster_year = pd.read_parquet(os.path.join(index_dir, "cluster_year.parquet"))
        cluster_country = pd.read_parquet(os.path.join(index_dir, "cluster_country.parquet"))
        embeddings = np.load(os.path.join(index_dir, "cluster_embeddings.npy"))
        keyword_lookup = json.loads(Path(index_dir, 'keyword_lookup.json').read_text(encoding='utf-8'))

        if model is None:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(EMBEDDING_MODEL_NAME)

        members_path = os.path.join(index_dir, 'members.json')
        members = json.loads(Path(members_path).read_text(encoding='utf-8')) if os.path.exists(members_path) else None
        return cls(clusters, cluster_year, cluster_country, embeddings, keyword_lookup, model, members)

    def member_keywords(self, row_idx):
        if self.members is not None:
            return self.members[str(row_idx)]
        return sorted({kw for kw, row in self.keyword_lookup if row == row_idx})

    def row_for_keyword(self, keyword):
        if not hasattr(self, '_keyword_rows'):
            if self.members is not None:
                self._keyword_rows = {kw: int(row) for row, kws in self.members.items() for kw in kws}
            else:
                self._keyword_rows = dict(self.keyword_lookup)
        return self._keyword_rows.get(keyword)

    def cluster_row(self, row_idx: int) -> Dict[str, Any]:
        rec = self.clusters[self.clusters.row_idx == row_idx].iloc[0].to_dict()
        years = self.cluster_year[self.cluster_year.row_idx == row_idx][["year", "count"]]
        countries = self.cluster_country[self.cluster_country.row_idx == row_idx][["country", "count"]]
        # NB: use ["count"] not .count - DataFrame.count is a method, attribute access shadows the column
        rec["years"] = years.groupby('year')['count'].sum().to_dict()
        grouped = countries.groupby('country')['count'].sum().to_dict()
        rec["countries"] = country_counts(grouped)
        return rec


LEXICAL_SCORE_CUTOFF = 60  # below this, token_sort_ratio matches are noise, not typos


def _lexical_candidates(query: str, bundle: IndexBundle, top_k: int) -> List[int]:
    """
    RapidFuzz over the flat keyword vocabulary -> ranked list of row_idx (deduped).

    token_sort_ratio (not WRatio) - WRatio blends in partial_ratio, which on a
    134k-entry vocabulary of very short strings occasionally hands an unrelated
    cluster a fluke high score against a garbled query (e.g. some member phrase
    of an unrelated cluster scoring above the actually-related "Dynamic
    Catalysis" for the query "catalisys"). A hard score_cutoff additionally
    keeps genuinely weak matches out of the fused ranking entirely, rather than
    letting them occupy candidate slots just for being "least bad".
    """
    choices = [kw for kw, _ in bundle.keyword_lookup]
    matches = process.extract(query, choices, scorer=fuzz.token_sort_ratio,
                               score_cutoff=LEXICAL_SCORE_CUTOFF, limit=top_k * 3)
    ranked_rows = []
    seen = set()
    for _text, _score, list_pos in matches:
        row_idx = bundle.keyword_lookup[list_pos][1]
        if row_idx not in seen:
            seen.add(row_idx)
            ranked_rows.append(row_idx)
        if len(ranked_rows) >= top_k:
            break
    return ranked_rows


def _semantic_candidates(query: str, bundle: IndexBundle, top_k: int) -> List[int]:
    """Cosine similarity (dot product on normalized vectors) -> ranked row_idx list."""
    q_vec = bundle.model.encode([query])[0]
    q_vec = q_vec / (np.linalg.norm(q_vec) or 1.0)
    sims = bundle.embeddings @ q_vec
    top = np.argpartition(-sims, min(top_k, len(sims) - 1))[:top_k]
    top = top[np.argsort(-sims[top])]
    return top.tolist()


def search(query: str, bundle: IndexBundle, top_n: int = 10, candidate_k: int = 50,
           rrf_k: int = 60, lexical_weight: float = 2.0, semantic_weight: float = 1.0
           ) -> List[Dict[str, Any]]:
    """
    Hybrid search: fuse lexical + semantic ranked lists with weighted
    Reciprocal Rank Fusion (score = sum of weight/(rrf_k + rank) across the
    lists a cluster appears in). Returns up to top_n cluster payloads,
    richest match first.

    Lexical is weighted 2x semantic: once past LEXICAL_SCORE_CUTOFF it's a
    precise typo/substring match, whereas cosine similarity on short technical
    phrases has no clean absolute floor (a garbled non-word query still lands
    "close" to *something*), so an unweighted 50/50 fusion lets semantic noise
    outvote a confident lexical hit. Semantic still wins on pure synonym
    queries, where lexical contributes nothing at all.
    """
    query = query.strip()
    if len(query) < 2:
        return []

    lexical = _lexical_candidates(query, bundle, candidate_k)
    semantic = _semantic_candidates(query, bundle, candidate_k)

    fused: Dict[int, float] = {}
    for rank, row_idx in enumerate(lexical):
        fused[row_idx] = fused.get(row_idx, 0.0) + lexical_weight / (rrf_k + rank)
    for rank, row_idx in enumerate(semantic):
        fused[row_idx] = fused.get(row_idx, 0.0) + semantic_weight / (rrf_k + rank)

    ranked = sorted(fused.items(), key=lambda kv: (-kv[1], -bundle.clusters.iloc[kv[0]].total_count))
    results = []
    for row_idx, score in ranked[:top_n]:
        payload = bundle.cluster_row(row_idx)
        payload["score"] = round(score, 5)
        results.append(payload)
    return results

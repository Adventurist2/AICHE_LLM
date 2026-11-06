# Scripts

> Historical August 16 scan. See [current.md](current.md) for the current
> aggregate, Ward clustering, index-building and Streamlit scripts.

## `Clustering.py`

- **Purpose:** Stage 6 — cluster a keyword-keyed JSON file with K-Means, no external API or ML library needed.
- **Inputs:** JSON file shaped like `aggregate.json`/`keywords_grouped.json` (top-level dict, keys = keyword strings, values = metadata dicts with `total_count`/`years`/`countries`).
- **Outputs:** `<output>.json` (default `clusters_output.json`) — cluster assignments, canonical keyword per cluster, top TF-IDF features per member, sorted by similarity to centroid.
- **Approach:** Hand-rolled TF-IDF (word unigrams + bigrams + character trigrams, sparse dict vectors) + hand-rolled K-Means++ with cosine-similarity assignment / Euclidean-distance seeding. No `numpy`/`sklearn` — pure stdlib (`json`, `math`, `random`, `collections`).
- **CLI:** `python Clustering.py <input.json> <k> [--output path.json]`
- **Status:** Active, self-contained, cheap to run (no API calls, no heavy deps) — good candidate for a quick smoke test of the repo.

## `group_keywords.py`

- **Purpose:** Stage 5, alternate implementation — same job as `keyword_grouping_2.ipynb` (rule-based dedup + semantic grouping of `aggregate.json`'s ~19k keywords) but calls the **Anthropic API** (`claude-sonnet-4-20250514`) directly via `urllib` instead of local Ollama.
- **Not directly runnable in this repo as committed:**
  - `INPUT_FILE`/`OUTPUT_FILE`/`LOG_FILE` are hardcoded to `/mnt/user-data/uploads/...` and `/mnt/user-data/outputs/...` — Linux sandbox paths (consistent with having been authored/run in a hosted code-execution sandbox, not this Windows checkout). The script's *output* (`keywords_grouped.json`, `grouping_log.txt`) was copied into the repo root; the script itself wasn't necessarily ever executed here.
  - `call_anthropic()` builds request headers with `Content-Type` and `anthropic-version` but **no `x-api-key` header** — as written, every call would fail auth. This looks like an artifact of wherever it actually ran (auth injected by that environment) rather than a bug to fix here.
- Contains the same `ABBREV_MAP` (chem-eng acronym expansions) duplicated across this file and both `keyword_grouping*.ipynb` notebooks — if one needs new abbreviations, all three currently need manual updates.
- **Status:** Reference/historical for how `keywords_grouped.json` was actually produced; not part of the runnable-in-this-repo pipeline.

# Repo Context — Index

**Last scanned commit:** `f856d9ddd54642a529ef3d3288792fc1261aa72d`
**Last scanned:** 2026-11-04 (current working tree, including uncommitted changes)

## Current implementation

Read [current.md](current.md) first. The sections below are an August 16
historical scan and predate the folder reorganization, semantic Ward clustering
and Streamlit explorer. `current.md` supersedes their current-state claims.

## What this repo is

A personal research pipeline that scrapes the AIChE annual conference program (confex.com), extracts chemical-engineering keywords and author/country metadata from each abstract using an LLM, then deduplicates/clusters those keywords for downstream analysis (geo trends, topic trends). It is **not** a packaged app — it's a working directory of Jupyter notebooks, two standalone scripts, and a large number of JSON data dumps at every pipeline stage, several years deep (2014, 2015, 2016, 2018, 2023 (default/unsuffixed), 2024).

There is no requirements.txt/environment.yml — dependencies are installed ad hoc into `.conda/` (a full embedded Windows conda env) as notebooks are run. `.env` holds live `GROQ_API_KEY*` / `OPENROUTER_API_KEY*` credentials (see [config.md](config.md)).

**As of the last scan, `groq.ipynb` is an in-progress live run** (actively appending to `extraction_process_groq.log`, `quota_monitor.log`, and `groq/extracted_results_2015/`) — see [notebooks.md](notebooks.md).

## Read next

| File | Covers |
|---|---|
| [pipeline.md](pipeline.md) | End-to-end stage-by-stage data flow, which file feeds which |
| [notebooks.md](notebooks.md) | Every `.ipynb`, what it does, active vs superseded |
| [scripts.md](scripts.md) | `Clustering.py`, `group_keywords.py` |
| [data.md](data.md) | Every top-level data directory: producer, consumer, year, format |
| [config.md](config.md) | Env vars (names only), external services/models, sensitive-file patterns |

## Top-level things worth knowing immediately

- **Readme.md is stale.** It describes a "Phase I/II/III" roadmap (`llama.ipynb` → `ollama.ipynb` → `open_router.ipynb`) as if those files live at repo root. They don't — they're archived in `catch/` and have been superseded by the current pipeline, which runs on **Groq** (`groq.ipynb`), not OpenRouter or local Ollama. The Readme predates that switch.
- **`groq copy.ipynb` and `groq copy 2.ipynb` are byte-identical frozen snapshots** of an earlier `groq.ipynb` state. `groq.ipynb` itself is the live, actively-edited file — it has 5 cells representing 3 successive rewrites of the same extraction logic (single-key → rate-limited single-key → **multi-key failover, the version currently in use**, see [notebooks.md](notebooks.md#groqipynb)).
- **`keyword_grouping.ipynb`, `keyword_grouping_2.ipynb`, and `group_keywords.py` are three parallel implementations** of the same "dedupe 19k keywords" problem — two use a local Ollama model, one uses the Anthropic API and has hardcoded `/mnt/user-data/...` sandbox paths (written/run somewhere other than this repo, its output copied in). See [pipeline.md](pipeline.md).
- **`catch/` is a graveyard/scratch folder** — archived notebook versions, old extraction results, and a `notepad/` subfolder that's gitignored. Treat anything there as reference, not active pipeline.
- **`UGP-20260320T132230Z-1-001/UGP/`** is a self-contained, separate side-project (its own `groq.ipynb`, geocoding CSVs, affiliation-suggestion CSVs) exported from Google Drive at some point. Not wired into the root pipeline.
- **No secrets are copied into any `context/*.md` file** — see [config.md](config.md) for the rule and what's tracked instead.

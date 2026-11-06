# Pipeline — end-to-end data flow

> Historical August 16 scan. See [current.md](current.md) for the current
> stage folders, independent grouping/clustering branches and threshold explorer.

Six stages. Not every stage has one canonical implementation — see the "alternates" notes.

```
Stage 1  Scrape AIChE Confex          aiche.ipynb
         -> sessions_*.json / sessions/sessions_<program>.json
         -> presentation_links_*.json (session URL -> paper URLs)
         -> aiche_file*/aiche_papers_<program>.json  (full paper records)

Stage 2  Chunk large program files    file_management.ipynb
         -> aiche_file_<year>_output/*_p<N>.json  (arrays split into
            80-record chunks — this is the shape groq.ipynb's batch
            reader expects)

Stage 3  LLM keyword extraction       groq.ipynb  (live/current)
         reads aiche_file_<year>(_output)/*.json
         -> groq/extracted_results_<year>/ext_*.json (per-file checkpoints)
         -> groq/extracted_results_<year>/final_combined_keywords_groq.json

Stage 4  Aggregate across all papers  keyword_processor.ipynb ("aggregate.py")
         reads all extracted_results_*/*.json
         -> aggregate.json  (19,592 keyword entries: total_count, years,
            countries, authors, papers_by_year)

Stage 5  Dedupe / group keywords      THREE alternate implementations, same job:
           - keyword_grouping_2.ipynb  (Ollama, local, refined/current)
           - keyword_grouping.ipynb    (Ollama, local, earlier version)
           - group_keywords.py         (Anthropic API — written for a
             different sandboxed environment, hardcoded /mnt/user-data
             paths; its OUTPUT was copied into this repo, the script
             itself is not runnable here as-is)
         reads aggregate.json
         -> keywords_grouped.json + grouping_log.txt (+ missed_keywords.txt
            for batches that failed to parse)

Stage 6  Cluster keywords (no API)    Clustering.py
         reads a keyword-keyed JSON (e.g. aggregate.json / keywords_grouped.json)
         -> clusters_output.json (K-Means over TF-IDF word/char n-grams,
            picks a canonical keyword per cluster)
```

`create_db.ipynb` is a side branch off Stage 4/5 output — it upserts `keyword_aggregate_all_results.json`-shaped data into a Postgres `keyword_stats` table. Uses hardcoded local dev credentials (`postgres`/`mysecretpassword`, `pguser`), redefined 3 times across its 6 cells in slightly different ways. No evidence of downstream consumption of the DB — nothing else in the repo reads from Postgres. Treat as experimental/exploratory, not part of the main flow.

## Per-year state (as of last scan)

| Year | Stage 1 raw | Stage 2 chunked | Stage 3 extracted |
|---|---|---|---|
| 2023 (unsuffixed) | `aiche_file/`, `sessions/`, `presentation_links/` | `aiche_file_output/` (**empty** — never chunked, or chunking output cleared) | `groq/extracted_results/` |
| 2014 | `aiche_file_2014/` | `aiche_file_2014_output/` | `groq/extracted_results_2014/` |
| 2015 | `aiche_file_2015/` | `aiche_file_2015_output/` | `groq/extracted_results_2015/` (**actively being written** — live run) |
| 2016 | `2016/` (non-standard name — `papers_Session*.json`, not `aiche_papers_*.json`) | `aiche_file_2016_output/` | `groq/extracted_results_2016/` |
| 2018 | `aiche_file_2018/` | `aiche_file_2018_output/` | `groq/extracted_results_2018/` |
| 2024 | `aiche_file_2024/` | `aiche_file_2024_output/` | `groq/extracted_results_2024/` |

`extracted/` at repo root (`aiche_papers_*_full_results.json`) looks like an older/alternate Stage-3-ish output naming convention, separate from `groq/extracted_results*`. `catch/` holds earlier attempts at Stage 3 via OpenRouter/Ollama (`catch/openrouter*/`, `catch/groq_results/`, `catch/groq_failover_results/`) predating the current multi-key-failover `groq.ipynb`.

## Archived alternate Stage-3 implementations (in `catch/`, superseded)

These match the Readme's "Phase I/II/III" roadmap, but that roadmap is what the project *started* as, not what it currently runs:

- **`catch/llama.ipynb`** — local inference via `transformers`/`torch`/`bitsandbytes`, 8-bit quantized Mistral-7B/Zephyr-7B.
- **`catch/ollama.ipynb`** — local serving via Ollama + Llama 3, structured-JSON prompting.
- **`catch/open_router.ipynb`** — cloud gateway to Mistral-7B-Instruct via OpenRouter, includes a `query_faiss.py`-tagged cell (FAISS-based retrieval, not otherwise referenced in the repo) and a `build_aggregate.py`-tagged cell (an OpenRouter-era precursor to `keyword_processor.ipynb`).

All three were replaced by `groq.ipynb` for speed/cost reasons (Groq's inference is notably faster; the current version's docstring-equivalent comments emphasize multi-key failover to survive per-key rate limits, which is why 15 `GROQ_API_KEY*` variables exist in `.env`).

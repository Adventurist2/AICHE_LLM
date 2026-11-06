# Data directories

> Historical August 16 scan. See [current.md](current.md) for the current
> folder layout, larger aggregate and per-threshold explorer snapshots.

Format reference: raw paper records (Stage 1) are JSON arrays of `{url, topic, date_time, abstract, presenting_author, authors, authors_structured}`. Session/link files are Stage-1 intermediates. Extracted-keyword files (Stage 3) are JSON arrays of `{title, authors, keywords, countries, source_file, Year}`. `aggregate.json`/`keywords_grouped.json` (Stage 4/5) are JSON dicts keyed by keyword string.

## Root-level, current pipeline (2023/unsuffixed year unless named otherwise)

| Directory | Stage | Produced by | Consumed by | Notes |
|---|---|---|---|---|
| `aiche_file/` | 1 (raw) | `aiche.ipynb` | `file_management.ipynb`, `groq.ipynb` | 21 files, 2023 program papers |
| `aiche_file_output/` | 2 (chunked) | `file_management.ipynb` | `groq.ipynb` | **Empty** — never populated for 2023, or cleared |
| `sessions/` | 1 (raw) | `aiche.ipynb` | manual/debug | 22 files, `sessions_<program>.json` |
| `presentation_links/` | 1 (raw) | `aiche.ipynb` | `aiche.ipynb` (its own next stage) | 22 files |
| `aiche_file_2014/`, `aiche_file_2014_output/` | 1, 2 | `aiche.ipynb`, `file_management.ipynb` | `groq.ipynb` | 397 / 445 files |
| `aiche_file_2015/`, `aiche_file_2015_output/` | 1, 2 | same | `groq.ipynb` | 709 / 773 files. **2015 is the year currently being extracted** (see [notebooks.md](notebooks.md#groqipynb)) |
| `2016/` | 1 (raw, non-standard layout) | `aiche.ipynb` (adapted) | `file_management.ipynb`-equivalent, `groq.ipynb` | Named `papers_Session<id>.json`, not `aiche_papers_<program>.json` — 2016 was scraped session-by-session rather than program-by-program |
| `aiche_file_2016_output/` | 2 | — | `groq.ipynb` | 21 files, `papers_Session<id>_p1.json` — chunked from `2016/` |
| `aiche_file_2018/`, `aiche_file_2018_output/` | 1, 2 | same | `groq.ipynb` | 22 / 57 files |
| `aiche_file_2024/`, `aiche_file_2024_output/` | 1, 2 | same | `groq.ipynb` | 41 / 58 files |
| `extracted/` | ~3 (alternate naming) | unclear — likely an earlier naming convention for Stage 3 output | — | `aiche_papers_<program>_full_results.json`, 26 files. Not the same directory the current `groq.ipynb` writes to (`groq/extracted_results*`) |
| `groq/extracted_results/`, `_2014/`, `_2015/`, `_2016/`, `_2018/`, `_2024/` | 3 | `groq.ipynb` | `keyword_processor.ipynb` | Current Stage-3 output, one subdir per year (unsuffixed = 2023). `_2015` actively growing at scan time |
| `aggregate.json` (root) | 4 | `keyword_processor.ipynb` | `keyword_grouping*.ipynb`, `group_keywords.py`, `Clustering.py` | 12.5MB, 19,592 keyword entries |
| `keywords_grouped.json` (root) | 5 | `keyword_grouping_2.ipynb` (or v1/`group_keywords.py`) | downstream analysis (not yet found in a notebook — likely consumed manually/ad hoc) | 13.6MB |
| `grouping_log.txt`, `missed_keywords.txt` (root) | 5 | same | human review | Human-readable logs of what got grouped/what failed to parse |

## Archive / scratch

| Directory | What it is |
|---|---|
| `catch/` | Graveyard of earlier pipeline attempts: archived notebooks (`llama.ipynb`, `ollama.ipynb`, `open_router.ipynb`), old extraction outputs (`openrouter/`, `openrouter_extracted/`, `groq_results/`, `groq_failover_results/`, `open_router/`), a `New folder` (empty), and `notepad/` (gitignored — see `.gitignore`). Also holds `quota_monitor.log`/`extraction_process_groq.log` copies from an earlier run. Treat as reference only. |
| `completed/` | 49 entries — appears to be a "done" bucket of processed program-paper chunks (`aiche_papers_3305_p2.json` etc.) plus `2018/`, `2024/` subfolders. Relationship to the main per-year dirs above is not fully confirmed — likely a manual "finished/checked" staging area rather than a pipeline stage. |
| `dummy/` | 1 file (`aiche_sample.json`, same content as `catch/aiche_sample.json`) — small sample used as `INPUT_DIR` in `groq.ipynb` cell 0 for quick testing. |
| `UGP-20260320T132230Z-1-001/UGP/` | Self-contained side-project, Google-Drive-exported (folder name is a literal Drive export timestamp id). Has its **own** `groq.ipynb` plus geocoding/affiliation CSVs (`geocoded_locations*.json/csv`, `affiliation_suggestions.csv`, `abstracts_same_uni_multiple_authors.csv`). Not wired into the root pipeline — separate effort, possibly an earlier academic-project (UGP = "Undergraduate Project") deliverable. |

## Root artifacts not covered above

- `quota_monitor.log` (23MB), `extraction_process_groq.log` (112KB at root) — live logs from the current `groq.ipynb` failover run (cell 4 writes to `quota_monitor.log`; cells 0/2 write to `extraction_process_groq.log`). Both grow every run; don't treat their size as meaningful, and don't commit them if avoidable (already tracked at HEAD, so they're not gitignored — worth revisiting).
- `grouping_log.txt` (67KB), `missed_keywords.txt` (347KB) — Stage 5 human-readable output, see table above.

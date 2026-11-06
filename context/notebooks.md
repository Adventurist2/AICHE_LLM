# Notebooks

> Historical August 16 scan. See [current.md](current.md) for relocated notebook
> paths, current extraction models and the current pipeline.

## `aiche.ipynb`

- **Purpose:** 3-stage Selenium + BeautifulSoup scraper of `aiche.confex.com`'s conference program.
- **Inputs:** Live web pages (`ModuleProgramBook`, `Program/<id>`, `Session/<id>`, `Paper/<id>` on `aiche.confex.com/aiche/2023/meetingapp.cgi/`).
- **Outputs:** `sessions.json` / `sessions_*.json` (calendar+session listing), `presentation_links_by_session_*.json` (session URL → paper URLs), `aiche_papers_<program>.json` (per-paper: url, topic, date_time, abstract, presenting_author, authors, authors_structured with per-author affiliation+designation).
- **Key libs:** `selenium` (Chrome webdriver), `beautifulsoup4`.
- **Status:** Active — this is Stage 1 of the pipeline (see [pipeline.md](pipeline.md)). Only 6 cells but the file is 2.2MB because of embedded print-log output from full scraping runs (not because of large source code).
- **Note:** headless mode is commented out in most cells (`# options.add_argument("--headless")`) — as committed, running this opens a real Chrome window.

## `file_management.ipynb`

- **Purpose:** Splits large per-program paper-array JSON files into fixed-size chunks (default 80 records) so downstream extraction can checkpoint per-chunk.
- **Inputs:** `aiche_file_2015/*.json` (hardcoded `INPUT_DIR` in the `__main__` block — edited by hand per year/run).
- **Outputs:** `aiche_file_2015_output/*_p<N>.json`.
- **Status:** Active, single cell, no external deps beyond stdlib. Re-run manually with `INPUT_DIR`/`OUTPUT_DIR` edited for each year.

## `groq.ipynb`

- **Purpose:** Stage 3 — LLM keyword + author-country extraction from paper abstracts via the Groq API.
- **Structure:** 5 cells = 3 successive full rewrites of the same logic, kept side by side instead of being deleted:
  1. **Cell 0** — original single-key version, model `llama-3.3-70b-versatile`, writes to `groq/extracted_results`.
  2. **Cell 2** ("code version 2") — adds a manual `GroqLimiter` (RPM throttle), switches model to `openai/gpt-oss-120b`, targets `aiche_file` → `groq/extracted_results`.
  3. **Cell 4** ("multiple accounts", marked "Work on this currently") — **the active version**. Builds a `FailoverMonitor` over up to 11 `GROQ_API_KEY*` env vars, cycling through both models (`llama-3.3-70b-versatile`, `openai/gpt-oss-120b`) per key on 429s, logging live quota headers (`x-ratelimit-remaining-requests/tokens`) to `quota_monitor.log`. Skips files whose output already exists (`ext_<file>.json`), so it's resumable/idempotent. Currently configured for `aiche_file_2015_output` → `groq/extracted_results_2015`.
- **Prompt contract:** system prompt asks for 5–10 specific chem-eng keywords + unique author countries, one-shot example included, output parsed via regex `\{.*\}` JSON extraction (tolerant of chatty model output).
- **Status: LIVE / IN PROGRESS as of the last scan** — `extraction_process_groq.log`, `quota_monitor.log`, and `groq/extracted_results_2015/` were all actively growing at scan time. **Do not assume this notebook is idle; check file mtimes before treating its output as final.**
- **`groq copy.ipynb` / `groq copy 2.ipynb`** are byte-identical (62,809 bytes) frozen snapshots of `groq.ipynb` from an earlier point (before cell 4's key list grew and before the model/logic in cells 0/2 were last touched). Treat as historical, not living code — don't edit them expecting it to matter.

## `create_db.ipynb`

- **Purpose:** Experimental — upsert extracted-keyword JSON (`keyword_aggregate_all_results.json` / `combined.json`) into a Postgres `keyword_stats` table via `psycopg2`.
- **Inputs:** DB connection via `PGHOST`/`PGPORT`/`PGDATABASE`/`PGUSER`/`PGPASSWORD` env vars, with **hardcoded local-dev fallback defaults** (`postgres`/`mysecretpassword`, later `pguser`/`mysecretpassword`) baked directly into 3 of its 6 cells — these look like disposable local Docker-Postgres creds, not real secrets, but are still hardcoded plaintext in a notebook.
- **Status:** Experimental / not integrated — nothing else in the repo reads from Postgres. Cells re-define the same connect-and-upsert logic three times with minor variations (looks like iterative debugging left in place rather than cleaned up).

## `keyword_processor.ipynb`

- **Purpose:** Stage 4 — "aggregate.py": scans a folder of extracted-keyword JSON files and builds the raw `aggregate.json` (keyword → total_count / years / countries / authors / papers_by_year). Pure aggregation, no embedding or LLM calls.
- **Usage (per its own docstring):** `python aggregate.py <input_folder> [raw_output_file]`.
- **Status:** Active, 2 cells (second cell is empty). Upstream of both grouping notebooks and `group_keywords.py`.

## `keyword_grouping.ipynb`

- **Purpose:** Stage 5 (v1) — dedupe/group the ~19k keywords in `aggregate.json` using (1) rule-based normalization (unicode/plural/abbreviation folding via a large `ABBREV_MAP` of chem-eng acronyms) then (2) semantic grouping of whatever's left via a **local Ollama** model.
- **Requires:** `ollama serve` running locally + model pulled (`llama3.2` per the configured `OLLAMA_MODEL`, though one leftover debug cell calls `ollama.chat(model='llama3', ...)` — inconsistent with the configured model name).
- **Outputs:** `keywords_grouped.json`, `grouping_log.txt`.
- **Status:** Superseded by `keyword_grouping_2.ipynb` (cleaner rewrite, see below) but still present/runnable.

## `keyword_grouping_2.ipynb`

- **Purpose:** Stage 5 (v2, current) — same rule-based + Ollama semantic grouping as v1, refactored: no leftover debug cells, adds `missed_keywords.txt` for batches that fail to parse/timeout (so they're not silently dropped), richer tqdm progress bar with live ok/fail/group counts.
- **Requires:** Same as v1 — local `ollama serve` + `llama3.2` pulled.
- **Status:** Active/preferred version of Stage 5's Ollama-based path. `group_keywords.py` (see [scripts.md](scripts.md)) is a third, Anthropic-API-based implementation of the same stage, written for/run in a different (non-Windows, sandboxed) environment.

## Archived, in `catch/` (superseded — see [pipeline.md](pipeline.md) for how these relate to the Readme's Phase I/II/III)

- **`catch/llama.ipynb`** — local quantized inference (`transformers`/`torch`/`bitsandbytes`, Mistral-7B/Zephyr-7B), plus a pasted-in "recent open router code" cell and geocoding-adjacent cells. Mixed/grab-bag notebook, multiple unrelated code versions pasted into sequential cells.
- **`catch/ollama.ipynb`** — multiple Ollama-based extractor versions pasted in sequence (cells explicitly annotated by the user as "the one I used" vs "not used").
- **`catch/open_router.ipynb`** — OpenRouter-based extractor, plus a `build_aggregate.py`-tagged cell (OpenRouter-era precursor to `keyword_processor.ipynb`) and a `query_faiss.py`-tagged cell (FAISS retrieval — not referenced anywhere else in the repo).

These three were not deep-read cell-by-cell (they're dense multi-version scratch notebooks); the above is a structural summary from cell headers/comments. Re-scan them individually if you need their exact code.

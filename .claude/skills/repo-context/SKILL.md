---
name: repo-context
description: Use when the user asks to "learn the repo", "map the codebase", "update repo context", "refresh context", "document what this repo does", "onboard to this project", or asks what a specific notebook/script/data folder does. Also use PROACTIVELY, without being asked, right after you (Claude) create a new notebook/script, rename or restructure files, add a new pipeline stage, or otherwise materially change what this repository does or how data flows through it — to keep the persisted context current. Builds and incrementally maintains a deep, current map of this repo's notebooks, scripts, data pipeline, and external dependencies in context/.
---

# Repo Context

## Why this exists

This repo is a loosely-organized collection of Jupyter notebooks and scripts implementing a multi-stage pipeline (scrape AIChE conference session/presentation data → extract keywords & author metadata via LLMs → group/cluster keywords → visualize). There is no CLAUDE.md, and file names alone (`groq.ipynb`, `groq copy.ipynb`, `groq copy 2.ipynb`, `aiche.ipynb`, `create_db.ipynb`, `keyword_grouping.ipynb`, `keyword_grouping_2.ipynb`...) don't reveal which files are live vs stale, or how data actually flows between them. This skill keeps a persisted, current map in `context/` so a future session (or a future you) doesn't have to re-open every notebook to re-derive that.

## Output location

- `context/INDEX.md` — top-level map, links to the files below, and scan metadata (`Last scanned commit`, `Last scanned date`)
- `context/pipeline.md` — end-to-end data flow across stages, stage by stage
- `context/notebooks.md` — per-notebook breakdown
- `context/scripts.md` — per-`.py`-script breakdown
- `context/data.md` — data directory map: what each dir holds, which stage produces/consumes it
- `context/config.md` — env var **names** used and by what, external services/models targeted, sensitive-file patterns already gitignored

If a topic would be near-empty, fold it into `INDEX.md` instead of creating a near-empty file.

## Hard rule: never leak secrets

This repo has history of committing secrets (see commit "Remove secrets from tracked files"). When documenting `.env`, config, or API usage:
- Record variable **names** only (e.g. `OPENROUTER_API_KEY`, `GROQ_API_KEY`), never values.
- Never paste contents of `.env`, `*.key`, `credentials.json`, `secrets.json`, or similar.
- If a hardcoded key/token turns up while reading a notebook or script, tell the user immediately — don't just quietly note it in context.

## First run (no `context/INDEX.md` yet)

Full scan:
1. `git log --oneline -20` and a root directory listing to inventory top-level files/folders.
2. Classify each entry: notebook, script, data-in, data-out, log/artifact (skip these), doc.
3. Read every live notebook and script (see "Reading notebooks cheaply" below) and summarize: purpose, inputs read, outputs written, external services/models called, key functions, and whether it looks superseded/stale (e.g. duplicate `groq copy*.ipynb` files — figure out which is canonical).
4. For each data directory, sample 1–2 files rather than reading everything, to learn schema/shape; note approximate file count instead of listing every file.
5. Reconcile against `Readme.md`'s stated roadmap (Phase I/II/III) — note where the actual code has diverged from what the Readme claims.
6. Write the five files listed above.
7. In `INDEX.md`, record `Last scanned commit: <hash>` and `Last scanned: <date>`.

## Update run (`context/INDEX.md` already exists)

Do **not** redo the full scan — incremental update only:
1. Read the recorded `Last scanned commit` from `INDEX.md`.
2. Run `git diff --stat <that_commit> HEAD` plus `git status` to get the exact set of files touched/added/removed since then (tracked changes + untracked files).
3. For each changed/added file, re-read just that file and update only the relevant section of the relevant topic file (`notebooks.md` / `scripts.md` / `data.md` / `config.md`).
4. For removed/renamed files, remove or update their stale entries.
5. If the change alters the pipeline's data flow (new stage, new downstream consumer of an output), update `pipeline.md`.
6. Bump `Last scanned commit` / `Last scanned` in `INDEX.md`.
7. If this run was triggered proactively — i.e. you just made the change yourself in this same session — skip the git-diff step, you already know exactly what changed; go straight to updating the relevant section(s).

## Reading notebooks cheaply

Notebooks like `aiche.ipynb` (2.2MB) and `groq.ipynb` contain heavy embedded outputs (dataframes, base64 images) that will blow up context if read raw with the Read tool. Extract only the source cells instead:

```bash
python -c "
import json, sys
nb = json.load(open(sys.argv[1], encoding='utf-8'))
for i, c in enumerate(nb['cells']):
    src = ''.join(c['source'])
    print(f'--- cell {i} [{c[\"cell_type\"]}] ---')
    print(src)
" "path/to/notebook.ipynb"
```

Use this for any notebook over ~100KB instead of the Read tool's raw JSON view.

## What each topic file should contain

**notebooks.md / scripts.md** — one subsection per file:
- Path
- One-line purpose
- Inputs (files/dirs read, APIs called)
- Outputs (files/dirs written)
- Key models/libraries (e.g. Mistral-7B via OpenRouter, Llama 3 via Ollama, Groq API, `transformers`/`bitsandbytes` quantization)
- Status: active / experimental / superseded (name what superseded it, if applicable)

**pipeline.md** — a stage-by-stage walkthrough (scrape → per-year raw session/presentation JSON → LLM keyword/metadata extraction → keyword grouping/clustering → geo/plot visualization), naming which script/notebook performs each stage and which file(s) hand off to the next stage.

**data.md** — per top-level data directory (`aiche_file_YYYY`, `aiche_file_YYYY_output`, `extracted`, `sessions`, `presentation_links`, `catch`, `completed`, `dummy`, plus root artifacts like `aggregate.json`, `keywords_grouped.json`): what it holds, which stage produces it, which stage consumes it, which year it corresponds to.

**config.md** — env var names used and by which files, external services (OpenRouter, Groq, Ollama) and which notebook targets which, `.gitignore` sensitive-file patterns already in place.

## Keep it a map, not a copy

Summarize logic; don't paste full code blocks into context files. Do call out quirks/gotchas that aren't obvious from file names alone (e.g. which `groq copy N.ipynb` is canonical, which `aiche_file_*_output` directories are actually populated vs empty scaffolding).

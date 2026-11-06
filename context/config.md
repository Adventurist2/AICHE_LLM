# Config, env vars, external services

> Historical August 16 scan. See [current.md](current.md) for current extraction
> models, runtime availability and dashboard dependencies. Credential values
> remain excluded from documentation.

**Reminder: this file records variable NAMES and service names only — never values.** See the hard rule in the `repo-context` skill definition (`.claude/skills/repo-context/SKILL.md`).

## `.env` (gitignored, present locally)

16 variables, all API keys for a multi-key failover rotation:

- `OPENROUTER_API_KEY`, `OPENROUTER_API_KEY1` … `OPENROUTER_API_KEY5` (6 total) — used by the archived `catch/open_router.ipynb`; not read by anything currently active.
- `GROQ_API_KEY`, `GROQ_API_KEY1` … `GROQ_API_KEY9` (10 total) — read by `groq.ipynb` cell 4 (`FailoverMonitor`), which builds its key list as `GROQ_API_KEY{0..10}` (`GROQ_API_KEY` for index 0, `GROQ_API_KEYn` for n=1..10). Only as many as exist in `.env` get loaded (falsy/missing ones are filtered out).

Loaded via `python-dotenv`'s `load_dotenv()` in every notebook cell that calls Groq/OpenRouter.

## External services / models referenced across the repo

| Service | Used by | Model(s) | Status |
|---|---|---|---|
| Groq API | `groq.ipynb` (all 3 cell versions) | `llama-3.3-70b-versatile`, `openai/gpt-oss-120b` (failover pair in the active cell) | **Active/current** |
| OpenRouter API | `catch/open_router.ipynb` | Mistral-7B-Instruct | Archived/superseded |
| Ollama (local, `localhost:11434`) | `keyword_grouping.ipynb`, `keyword_grouping_2.ipynb`, `catch/ollama.ipynb` | `llama3.2` (configured), stray `llama3` reference in one debug cell of v1 | Active for Stage 5 grouping; requires `ollama serve` running + model pulled |
| Anthropic API | `group_keywords.py` | `claude-sonnet-4-20250514` | Written for a different (sandboxed) environment; not directly runnable here — see [scripts.md](scripts.md) |
| Postgres | `create_db.ipynb` | n/a | Experimental, local dev only, hardcoded dummy creds — see [notebooks.md](notebooks.md#create_dbipynb) |

## `.gitignore` — sensitive-file patterns already in place

```
.env
.env.*
*.env
*.key
*.pem
*.p12
*.pfx
*.crt
*.cer
*.p8
*.secret
secrets.json
credentials.json
notepad/
catch/notepad/
```

Note: `.env` is excluded, but nothing in `.gitignore` excludes the large generated JSON/log artifacts (`quota_monitor.log`, `aggregate.json`, `keywords_grouped.json`, per-year `groq/extracted_results_*`, etc.) — those are all currently tracked in git at multi-MB sizes. Worth a deliberate decision (not made by this scan) about whether that's intended.

There is repo history of secrets having been committed and then removed (`f856d9d Remove secrets from tracked files`) — be extra careful not to reintroduce real key values into any tracked file, including this `context/` folder.

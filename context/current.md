# Current repository map — November 6, 2026

This summarizes the current project snapshot. No credentials are recorded here.

## November 6 publication status

The repository is being published on its existing `chandan` branch, with code,
datasets, archives, validation reports, aggregate snapshots, and web indices.
Large aggregate files and NumPy arrays use Git LFS. Local environments, model
caches, editor state, and credentials remain excluded. The root README includes
fresh-clone setup instructions.

The November 4 worker stopped at 21:58 that day with exit code 1073807364;
`reports/keyword_refresh_2026-11-04/refresh_status.json` records `failed`.
Its frozen 183,489-keyword input is retained, but its Ward tree and twelve-height
results did not complete or replace the live 173,438-keyword, five-height snapshot.
The running/pending descriptions below are historical November 4 progress notes.

## November 4 refresh (supersedes dated status notes below)

### Multipage UI and interpretation guide

`05_webapp/app.py` now uses native `st.navigation` with five file-based views:
Explorer `/`, Trends `/trends`, Geography `/geography`, Institutes `/institutes`,
and About & metrics `/about`. Shared loaders and rendering live in `dashboard.py`;
`about.py` explains metrics, calculations, examples, graph axes and significance,
non-normalized counts, clustering distances, geography caveats and source coverage.
The old single-page entrypoint is retained as `app_before_multipage.py.bak`.

Threshold and dark mode are global entrypoint widgets. The keyword is a permanent
session key; page-local scope and institute controls write through to permanent
session keys so native page navigation cannot discard those selections. Institute
views separate selected-theme attribution from directory browsing. Tests and
`verify_app.py` now navigate to the Institutes route to check its source-backed
counts, then return to Explorer. All eight regression tests passed, including
navigation through all five pages and state preservation. Full installed-data
checks passed all five current heights and exact-keyword mode. The pending larger
rebuild will run this updated verifier against all twelve prepared heights.
Live browser checks confirmed native top navigation, keyword carry-over to
Institutes and back, dark mode, and the About explanations. At 390px the
native navigation becomes a drawer; CSS now themes its background, links and
close control for dark-mode contrast. The viewport override was reset after
testing. Clustering controls collapse on secondary pages, and metric definitions
use readable expanders instead of horizontally clipped data-grid cells.

The October 13 rebuild finished and was installed at 22:56 that day. It covers
173,438 keywords and 313,858 mentions at five heights. Its completed status
and backup remain under `reports/keyword_refresh_2026-10-13/`.

The new frozen aggregate under `reports/keyword_refresh_2026-11-04/` has
183,489 unique keywords (10,051 added, none removed), 331,849 mentions and
all eleven meeting years 2014–2024. The 2017 extraction is partial: 78 output
files / 658 records / 35 keyword-bearing records. New files arriving after
the snapshot are outside this rebuild. 2021 includes 785 correct-year batches
and 5,776 records; 2022 has 710 batches and 5,910 records.

710 additional 2022 batches had also been extracted into the 2021 folder.
`prepare_snapshot.py` verifies actual input URL years against the archived
chunk files and excludes these wrong-year duplicates only when the correctly
filed 2022 counterpart exists. The originals are untouched; the full hash
manifest records each exclusion. 2021/2022 inputs now live under
`archive/completed/aiche_file_2021_output` and `aiche_file_2022_output`.
`institutions.py` includes those paths and the 2017 chunks, preserving
source-backed affiliation matching for the newly included years.

Default Ward cuts are now 0.25 / 0.40 / 0.50 / 0.60 / 0.75 / 0.90 / 1.00 /
1.25 / 1.50 / 2.00 / 2.50 / 3.00. The live slider auto-discovers them after
installation. `verify_app.py` now tests every prepared height rather than
five fixed heights. The completion worker runs regressions, full clustering,
staged preparation, index/provenance/UI audits, then installs the snapshot
with a rollback copy. Read the new `refresh_status.json` for actual progress;
do not assume the rebuild has completed from this note.

The registered `C:/Program Files/python.exe` no longer exists, and `.conda`
is Python 3.10 without clustering dependencies. `.runtime/python312` contains
the official Windows embeddable Python 3.12 runtime, checksum checked against
the Python release page. Its `_pth` reuses existing user Python 3.12 packages
and repo module directories. No system Python registrations were changed.
Use `.runtime/python312/python.exe` for this refresh and the local web app.
The old Hugging Face cache was also missing. The MiniLM model was restored
under `.runtime/huggingface`; set `HF_HOME` to that directory for manual app
launches (the worker sets it automatically). Re-encoding twelve cached terms
matched the saved vectors with minimum cosine 0.99999988, confirming cache
compatibility. All eight regression tests passed with the local runtime.

## October 13 keyword refresh

New Groq outputs include 2019, 2020 and a still-growing 2021 run, plus more
2015 results than the previously installed aggregate. A fixed snapshot under
`reports/keyword_refresh_2026-10-13/extractions/` contains all completed JSON
outputs captured at the start of the refresh. Its aggregate contains 173,438
unique keywords (58,971 added, none removed), 313,858 mentions and nine years.
The 2021 snapshot includes 90 output files / 612 records / 363 keyword-bearing
records; later extractions require a later rebuild. No completed 2017/2022
extraction folders were present when the snapshot was made.

The Ward producer (PID 13476) rebuilds the full 384-dimensional tree and all
five cuts under `reports/keyword_refresh_2026-10-13/clusters/`. The completion
worker (`complete_refresh.py`, initially PID 39628) waits for the matching
cuts, builds staged indices, runs the full index/institute/Streamlit audits,
and only then installs the aggregate, clusters and indices. It retains the
old live files under `previous_snapshot/` and starts the verified local app
if port 8501 is free. Read `refresh_status.json` for the actual current stage;
do not assume completion from this dated note. `build_summary.json` appears
after publication. Until publication, the installed baseline remains the
114,467-keyword, six-year snapshot described below.

`prepare_indices.py --output-dir` and `AICHE_INDEX_DIR` support validation of
a staged snapshot. `verify_institutions.py --aggregate` selects its matching
aggregate; `--source-only` audits attribution before clustering finishes.
New 2019 sources use `archive/UGP-side-project/UGP_2019_reparsed`; original
2020/2021 paper files were copied without changes from the organized Downloads
folders into `01_scraping/raw/UGP_2020` and `UGP_2021` for reproducible attribution.

The root `aiche_file_2021_output` contains 5,776 records with 2021 source URLs
and 5,910 records with 2022 URLs. It was not rearranged while extraction was
actively creating outputs. All 90 snapshotted 2021 output files were checked
against input URLs and contain 2021 source records. Institution loading and
its independent verifier now reject source URLs whose year differs from the
folder's year. Correct the mixed input folder before relying solely on its
name in subsequent extraction/aggregation runs.

The staged index contains `data_coverage.json` with its source fingerprint,
snapshot date, per-year processed-record counts and partial-year flags.
The app shows the partial extraction notice and coverage table only for a
matching snapshot. Eight regression tests passed for these changes, including
the coverage notice, maps, institute counts, slider and dark mode. Full new-data
audits will run before installation. `reports/professor_presentation_brief.md`
covers normalized topic trends, emerging themes, institute specialization,
collaboration/co-occurrence networks, methodology and limitations.

Source preflight passed for 383,742 attribution links, 29,599 matched papers
and all 263,326 keyword/paper pairs. New 2019 extraction titles use presentation
numbers absent from the API `title`, but present in the recorded `topic`.
Both exact recorded title fields are now indexed within the same source file
and year; no fuzzy matching was introduced. 6,845 of 6,857 2019 title/file
references matched; 12 ambiguous references were excluded. Preflight tables
and coverage are under `institution_preflight/`. Full installed-snapshot
checks still wait for Ward completion.

## Pipeline and runnable entry points

1. `01_scraping/aiche.ipynb`: Selenium/BeautifulSoup scraper for conference
   programs, sessions and papers. Raw JSON is under `01_scraping/raw/`.
2. Root `file_management.ipynb`: 80-paper chunks. Most historical chunks are
   under `01_scraping/chunked/`; 2015 raw and chunked directories are now under
   `archive/catch/` and `archive/completed/` (older runs used root paths).
3. Root `groq.ipynb`, cell 4: preferred multi-key failover extractor, configured
   for 2021, with `openai/gpt-oss-120b` / `openai/gpt-oss-20b`. Results are still
   under `groq/extracted_results*`. Existing output files are skipped. Saved
   records omit author names and hardcode `Year: 2023`; oversize requests and
   parsing failures may leave empty keyword lists. Do not assume a live kernel
   solely from old documentation; new output files were observed arriving on October 13.
4. `02_extraction/aggregate_keywords.py`: current combined aggregator, discovers
   per-year extraction folders and derives the year from folder names. The
   saved aggregate has 114,467 keywords / 201,463 keyword mentions over 2014,
   2015, 2016, 2018, 2023 and 2024. `keyword_processor.ipynb` is older and only
   aggregates one folder. Only 354 aggregate entries have author statistics.
5. Two independent consolidation branches read the aggregate:
   - `03_grouping/keyword_grouping_2.ipynb`: rule-based and Ollama synonym
     grouping. v1 and the Anthropic sandbox script are alternatives. The
     saved grouping output has 18,491 entries and predates the large aggregate.
   - `04_clustering/cluster_keywords.py`: all-MiniLM-L6-v2 embeddings, one Ward
     tree across all years, without dimensionality reduction. Embeddings and
     the tree are cached. Default cuts: 0.5 / 0.75 / 1.0 / 1.25 / 1.5;
     `--thresholds` accepts other positive heights. Results and labeling
     checkpoints are fingerprinted against the aggregate. Labels can come
     from Ollama, centroid-nearest keywords, or exact-member-set reuse via
     `--reuse-labels`. The older stdlib TF-IDF `Clustering.py` is superseded.
6. `05_webapp/prepare_indices.py`: checks a common source fingerprint, builds
   per-height indices via `build_index.py`, and writes compact keyword stats.
7. `05_webapp/app.py`: Streamlit slider switches search, members, trends,
   map and rankings together. A selected raw keyword anchors selection across
   heights; cluster row IDs are not stable between heights. Search combines
   RapidFuzz and semantic centroid ranking with weighted reciprocal rank fusion.

## Explorer preparation

From repo root:

```powershell
python 04_clustering/cluster_keywords.py --no-llm --output-dir 04_clustering/explorer_results --reuse-labels 04_clustering/clustering_results
python 05_webapp/prepare_indices.py
streamlit run 05_webapp/app.py
```

Current explorer artifacts live in `04_clustering/explorer_results/` and
`05_webapp/index/dt*/`, with shared `index/keyword_stats.json`. They are rebuilt
from the saved aggregate. Rebuild clustering and indices after editing that
aggregate. `05_webapp/README.md` documents extension to other cut heights.

Historical `04_clustering/clustering_results/` covers 104,458 keywords rather
than the 114,467-keyword aggregate. Its dt0.5 JSON is malformed; dt1.0 and dt1.5
are readable. The old flat `05_webapp/index/` files are also historical. The
new explorer uses its own fresh snapshot and does not load these flat indices.

The full rebuild completed October 1. All five explorer cuts cover 114,467
keywords and 201,463 mentions: 94,033 themes at 0.50; 61,664 at 0.75;
33,014 at 1.00; 18,832 at 1.25; 11,688 at 1.50. Every country/year rollup,
keyword assignment and hierarchy nesting passed the full-data verifier.
Streamlit checks also verified selection preservation, plotted map values,
and exact-keyword scope across all heights. The initial sandbox temp cleanup
warning was followed by a clean UI verification rerun with exit code 0.

## Country counts and statistics

`countries.py` sums spelling aliases before building the index. Previously,
`United States` and `USA` could become duplicate rows and `dict(zip(...))`
overwrote counts; 1,818 historical dt1.0 clusters had multiple US aliases.
`IndexBundle.cluster_row` also defensively groups duplicate country/year rows.
The map uses explicit ISO3 codes and displays the same counts in a table.
Unspecified `Korea` is preserved without guessing South Korea; unknown locations
remain in the table without a map color. "Whole theme" includes all members;
"One keyword" uses just that keyword's source counts. These are mentions,
not distinct papers, and countries remain those provided by LLM extraction.

## Institute and keyword attribution (October 3)

`05_webapp/institutions.py` adds a source-backed affiliation stage after keyword
aggregation. It joins `papers_by_year` references to exact cleaned titles within
the same year/source file, preferring raw records and falling back to chunks.
The 2015 sources may live at their old root paths or under
`archive/catch/aiche_file_2015` and `archive/completed/aiche_file_2015_output`.
Original author affiliations are recovered even though most Groq extraction
outputs omit authors. Abstract attachment URLs are excluded: historical 2014
scrapes sometimes incorrectly assigned them a neighboring paper title.
Ambiguous and missing title/source matches are reported rather than guessed.

Paper URLs deduplicate repeated session listings. Distinct institute/keyword/
paper links also prevent multiple authors at one affiliation from multiplying
paper counts. Exact organization names recorded in 2018/2023/2024 are used to
combine matching comma-delimited department/location strings, with campus
qualifiers preserved; unresolved variants retain the recorded affiliation.
Missing affiliations and placeholders are not invented or assigned institutes.
This is a conservative affiliation list, not a fully curated institution registry.

Shared outputs under `05_webapp/index/`: `institution_links.parquet`,
`institution_papers.parquet`, `paper_keywords.parquet`, `institution_meta.json`,
`institute_keywords.csv` and `institution_unmatched_records.csv`. The snapshot
is tied to the aggregate SHA256; the app rejects a mismatching affiliation
snapshot. Run `python 05_webapp/institutions.py` independently to refresh it
without rebuilding Ward; `prepare_indices.py` also invokes it for future runs.

Current coverage: 20,288 unique matched papers; 18,430 with affiliations;
105,813 linked keywords; 5,384 institute/affiliation display names (variants
can remain separate). 162 source-file/title references are unmatched or
ambiguous. The institute numbers measure distinct papers, whereas the existing
map and trend numbers measure keyword mentions.

The Streamlit selection shows institute rankings for either one keyword or
the current whole theme. The new **Institutes and keywords** tab displays an
institute's keyword counts/years and themes at the selected Ward height.
Both directions include source paper links, original affiliation text and
CSV downloads; all institute/keyword pairs are downloadable. Coverage is
visible by year. Unit checks cover source scoping, duplicates, attachment
exclusion, campus normalization and ambiguous records; UI checks cover institute
scope and distinct-paper counts as themes merge and split. `verify_app.py`
also checks the full-data institute lists across every slider height.
All seven unit/UI regression tests passed, and the real-data Streamlit verifier
passed institute, map and metric checks at all five heights and in exact-keyword
mode. Windows temporary-directory access required the existing scoped test
approval; the completed runs exited with code 0.

## Validation and infrastructure

### Dashboard refinement and audit (October 3)

The header now includes a **Dark mode** toggle. `ui.py` provides both palettes,
theme-aware chart/map colors and search-component style overrides; CSS tokens
change page surfaces, controls and text. Streamlit's neutral canvas tables use
a scoped dark presentation filter (the displayed values and exports are unchanged).
The preference is stored as `?theme=dark` / `?theme=light` via public query parameters
and restored on refresh, without changing selected keyword, clustering height or
count scope. Regression tests verify both palettes, selection preservation,
count consistency and restoration from the dark-mode URL.

The explorer now has a light teal theme in `.streamlit/config.toml`, with
presentation helpers in `05_webapp/ui.py` and `style.css`: grouped search and
height controls, compact metric cards, consistent Plotly charts, expandable
country tables/methodology and a responsive layout. At narrow widths, controls
and charts stack while metrics retain two columns. Example keyword buttons
set a fresh search state. Download buttons use `on_click='ignore'`; the complete
CSV bytes are cached by file modification time. Missing/corrupt optional
institution tables produce a warning while keyword search and maps continue.
The UI dependency versions are pinned to the installed, tested versions.

`05_webapp/verify_institutions.py` audits foreign keys, duplicate links, year
consistency, aggregate fingerprint, metadata/coverage totals, original author
affiliation provenance and all 229,482 rows of the institute/keyword CSV.
The strengthened full audit passed for 245,215 attribution links and 20,288 matched papers.
It independently checks every keyword/paper pair against the original
year/source-file/title reference and checks every shortened institute name
against complete comma-delimited parts of recorded affiliations. Four invalid
display names (phone/email contact fields) were removed from five paper-affiliation
records, eliminating 44 false links and export rows. Rejected contact values
and their sources are retained in `index/institution_excluded_affiliations.csv`.
Failed-scrape placeholder titles are excluded so that a successful source record
provides the supporting-paper title. Eight regression tests passed, as did the
full-data Streamlit checks at all five heights and in exact-keyword mode.
`index/institution_validation.md` summarizes the audit; the corresponding
`institution_validation_evidence.csv` traces the CO2-capture theme at 1.00 to
original paper links and affiliations. These checks establish provenance to
stored records, rather than independently certifying upstream scrape/extraction
accuracy or curating an organization registry.
The live browser's complete downloaded CO2-capture institute list at threshold
1.00 matched all 221 source-backed rows, including counts and keyword lists.
All seven regression tests passed, including institute switching, clearing the
selection and incomplete affiliation-data recovery. The full index verifier
passed every country/year rollup and nesting at all five heights; the Streamlit
verifier passed selected-keyword preservation, metrics, maps and institute
counts at each height and in exact-keyword scope.

Live browser checks cover actual search suggestions and selection, keyboard
threshold changes, exact-keyword scope, chart/map rendering and responsive
layout at 1280px and 390px. The downloaded 209-row institute list for the
CO2-capture theme at 0.75 matched the source-backed summary. Browser review
fixed header overlap, low caption contrast and Plotly's empty-title text.
The local app is served at `http://127.0.0.1:8501` for review.

`python -m unittest discover -s 05_webapp/tests -v` exercises alias summation,
legacy duplicate rows and keyword selection across heights. Windows sandbox
execution may require temp-directory access for these tests.
`python 05_webapp/verify_indices.py` checks every member assignment, source
country/year rollup, total count, embedding norm and nesting across heights.
Ward/HDBSCAN/K-Means comparison scripts and saved results remain under
`04_clustering/algorithm_comparison/`.

`05_webapp/requirements.txt` lists dashboard dependencies; clustering also
needs scipy, fastcluster and optionally Ollama. The working dependencies in
this session are available through system Python; the embedded `.conda/`
environment lacks them. `.env` remains gitignored; extraction uses variable
names `GROQ_API_KEY` / numbered variants. Local inference experiments,
OpenRouter code, database exports, frozen copies and the geocoding side project
are under `archive/` and are not the primary explorer workflow.

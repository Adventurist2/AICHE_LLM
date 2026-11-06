# AIChE Keyword Trend Explorer

The interface has five native pages, with direct URLs and top navigation:

- **Explorer** (`/`): search, selected-theme metrics, time series and map.
- **Trends** (`/trends`): themes ranked within a meeting year.
- **Geography** (`/geography`): themes ranked for a reported country.
- **Institutes** (`/institutes`): selected-theme affiliations or an institute directory,
  with supporting papers and downloads.
- **About & metrics** (`/about`): definitions, calculations, worked examples,
  graph significance, clustering methods, extraction coverage and limitations.

Keyword, threshold, count scope and appearance persist across page changes.
The threshold and appearance widgets belong to the global app frame. Page-local
scope/institute widgets save their selections outside widget state so Streamlit
does not discard them when those widgets leave the current page.
`dashboard.py` contains shared data/rendering helpers; `views/*.py` defines the
file-based routes and `about.py` contains the reading guide. Tables and supporting
details use bounded grids or expanders to keep the pages focused.

From the repository root:

```powershell
python 04_clustering/cluster_keywords.py --no-llm --output-dir 04_clustering/explorer_results --reuse-labels 04_clustering/clustering_results
python 05_webapp/prepare_indices.py
python -m streamlit run 05_webapp/app.py
```

The clustering job builds one Ward tree, caches it, and cuts it at **0.25,
0.40, 0.50, 0.60, 0.75, 0.90, 1.00, 1.25, 1.50, 2.00, 2.50, and 3.00**.
Lower heights create finer themes; higher heights create broader themes.
These are Ward linkage distances, not percentages or confidence scores.
Use `--thresholds` to add other positive heights,
then rebuild the indices. The slider discovers all prepared heights. Changing
it switches search, trends, map, keyword members and rankings together. The
selected member keyword is carried into its theme at the new height.

New clusters use a centroid-nearest keyword as their label. Existing generated
labels are reused only when the entire member set matches. For a new run, omit
`--no-llm` to generate labels with local Ollama; this takes longer. For existing
results, add `--force` to regenerate labels (the matching Ward tree is reused).
Cached results and label
checkpoints are tied to the aggregate fingerprint, preventing stale counts and
labels from being silently reused after the source changes.

`explorer_results/` and `index/dt*/` contain the current explorer snapshot;
the old `clustering_results/` and flat `index/` files are historical artifacts.
Run both preparation commands after changing the aggregate. The app rejects
mixed clustering and keyword-statistics snapshots.

Country aliases are **summed**, not overwritten. The map uses explicit ISO3
codes, and its table shows the same counts. Ambiguous locations (such as
unspecified `Korea`) and unknown locations stay visible in the table without
being assigned a guessed country. "Whole theme" includes every member keyword;
"One keyword" uses that keyword's own year and country counts. Counts measure
keyword mentions, not distinct papers, and retain the upstream extraction's
country assignments; these changes do not independently geocode affiliations.

The interface uses a light theme with a restrained teal accent, grouped search
and threshold controls, compact metric cards and consistent charts. Country
counts and detailed methodology are expandable. Narrow screens stack the
controls and charts and retain two columns of metric cards. Example keyword
buttons provide a quick starting point; downloads preserve the current view
without rerunning the app. `.streamlit/config.toml` sets the theme, while
`05_webapp/style.css` and `ui.py` contain presentation defaults.

The **Dark mode** switch beside the app heading changes the page, controls,
search dropdown, charts, map and data tables. The selection is retained in the
page URL so it survives a refresh. It does not change selected keywords,
thresholds or count scopes.

The dependencies in `05_webapp/requirements.txt` are pinned to the versions
used for the dashboard checks. For a new environment, install them with
`python -m pip install -r 05_webapp/requirements.txt`. The prepared index files
and the sentence-transformer model cache are also needed; the model is
downloaded on first use if it is not cached.

The **Institutes and keywords** tab lets you select an institute / recorded
affiliation and see its keywords, distinct paper counts, years and research
themes at the selected threshold. A searched keyword or theme also displays
its contributing institutes. Both views include supporting paper links,
original affiliation strings and CSV downloads. The complete list is saved
as `05_webapp/index/institute_keywords.csv`.

Institute attribution uses the aggregate's paper references to match original
scraped titles within the same year and source file, using either exact
recorded `title` or `topic` text (some years include a
presentation number only in `topic`). The loader rejects original paper URLs
whose year disagrees with the source-year mapping. Paper URLs deduplicate
repeated session listings, and coauthors at one institute do not multiply
paper counts. Abstract attachment URLs are excluded because historical
scrapes sometimes gave them a neighboring presentation's title. Missing and
ambiguous matches are omitted and reported in the coverage table and
`institution_unmatched_records.csv`. Missing affiliations are never inferred.
Exact organization names present in newer records combine matching department
and location strings; remaining variants retain their recorded names, so this
is an affiliation list rather than a fully curated registry of institutions.

To rebuild only the institute data, without rebuilding Ward clustering:

```powershell
python 05_webapp/institutions.py
```

`prepare_indices.py` also builds this shared institute snapshot. Its aggregate
fingerprint must match the selected clustering and keyword statistics. Institute
counts are **distinct papers** and can differ from the map's keyword mentions.

The November 4 refresh freezes completed extraction results, removes duplicate
2022 batches wrongly filed under 2021, and rebuilds all twelve heights from
the corrected snapshot. Progress is recorded in
`reports/keyword_refresh_2026-11-04/refresh_status.json`. Installation happens
only after regression, full index, institute-provenance and all-height UI
checks pass. The preceding dataset is kept under `previous_snapshot`.

The old system Python executable is missing on this machine. A project-local
Python runtime is available at `.runtime/python312/python.exe`, configured to
reuse the existing user-installed Python 3.12 packages. For example:

```powershell
$env:HF_HOME = Join-Path (Get-Location) '.runtime\huggingface'
& .\.runtime\python312\python.exe -m streamlit run 05_webapp/app.py
```

Regression checks:

```powershell
python -m unittest discover -s 05_webapp/tests -v
python 05_webapp/verify_indices.py
python 05_webapp/verify_institutions.py
python 05_webapp/verify_app.py
```

The affiliation verifier checks table integrity, years, original affiliation
provenance and every row of the complete CSV export. It independently resolves
every keyword/paper reference by year, source file and exact title, and verifies
that each institute display name is present in an original affiliation.
Phone-only, email/contact-led and web-contact values are excluded, with their
source trail in `index/institution_excluded_affiliations.csv`. Failed-scrape
placeholder titles cannot replace successful supporting-paper records.
The audit writes `index/institution_validation.md` and
`index/institution_validation_evidence.csv` for the CO2-capture theme at 1.00.
This validates the saved conference records, not an independently curated
institution registry; upstream scrape/extraction errors and name variants can
remain. UI checks exercise all five heights, keyword/theme scopes and incomplete
optional institute data.

For a staged refresh, pass `--output-dir PATH` to `prepare_indices.py`. Set
`AICHE_INDEX_DIR` to that index directory while running verifiers, and pass
the matching `--aggregate PATH` to `verify_institutions.py`. `--source-only`
can validate affiliations before the Ward cuts are ready. The normal app
continues to use `05_webapp/index` when the environment override is absent.

When a snapshot includes `data_coverage.json`, the app shows its capture date,
partial extraction years and per-year processed-record coverage. This metadata
must match the keyword aggregate fingerprint. Counts from partially extracted
years should not be used to claim a fall in research activity.

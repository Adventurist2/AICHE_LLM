# AIChE Research Atlas: professor presentation brief

Prepared October 13, 2026. The new snapshot is being clustered; the existing
website dataset remains installed until the replacement passes validation.

## What the project does

The pipeline turns conference paper abstracts into searchable research themes.
It combines keywords across years, embeds them using all-MiniLM-L6-v2, builds
one Ward hierarchical clustering tree, and presents several cuts of that tree
in a Streamlit explorer. Users can search a keyword, vary the clustering
height, inspect trends and countries, and trace institute results to papers.

The frozen refresh contains **173,438 unique keywords**, **313,858 keyword
mentions**, and nine meeting years: 2014, 2015, 2016, 2018, 2019, 2020, 2021,
2023 and 2024. It adds **58,971 keywords** to the previously installed snapshot.
2021 is a partial extraction: this refresh includes 90 completed output files.
There are no completed 2017 or 2022 extraction folders in this snapshot.
Extraction coverage differs across years, so the dataset is an observed
conference sample, rather than a complete census of chemical-engineering research.

## Analyses to prioritize

| Analysis | Research question | How to calculate it | Presentation visual |
|---|---|---|---|
| Normalized topic trends | Which themes gain a larger share of the observed research? | For each year, count distinct matched papers containing a theme and divide by distinct matched keyword-bearing papers that year. Show matched-paper coverage; alternatively use a clearly labeled share of keyword mentions. | Topic-by-year heatmap and a few trend lines |
| Emerging and declining themes | Which established themes grew, and which were first observed recently? | Compare normalized shares across covered years, require a minimum paper count, and distinguish first observed in this dataset from genuinely new research. Exclude partial 2021 from growth rankings. | Growth-versus-volume scatterplot |
| Institute specialization | What does each institute concentrate on? | Divide its fraction of papers in a theme by the corresponding fraction across all matched papers. Show this specialization ratio alongside paper counts and require a minimum sample size. | Institute-by-theme heatmap |
| Collaboration patterns | Which institutes work together, and on which themes? | Count distinct source papers with authors from both institutes. Review affiliation aliases first, credit each institute pair once per paper, and exclude ambiguous organization strings. | Weighted collaboration network |
| Connections between topics | Which ideas repeatedly appear together? | Count keyword/theme pairs occurring in the same source paper, remove duplicate keywords per paper, and compare association strength with the pair's individual frequencies. | Co-occurrence network or matrix |
| Clustering evaluation | How do narrow and broad themes differ, and are they coherent? | Compare size distributions and singleton shares at 0.50/0.75/1.00/1.25/1.50. Inspect 30–50 clusters across sizes and review keywords plus supporting abstracts with a domain expert. | Cluster-size chart and examples of merges |

For the first presentation, prioritize **normalized trends**, **institute
specialization**, and **clustering evaluation**. Together they demonstrate
research findings, practical use, and methodological care. Collaboration and
topic networks are strong next extensions after affiliation names are reviewed.

## Explain the method clearly

- Keywords use 384-dimensional sentence embeddings; Ward clustering runs on
  those embeddings without PCA/UMAP reduction.
- All years share one tree, so a keyword has one membership at a given height.
- The five cut heights provide narrower or broader themes. A height of 0.75
  is a Ward distance threshold; it does **not** mean 75% similarity or confidence.
- Labels are centroid-nearest member keywords, with older labels reused only
  for identical member sets. A label is a browsing aid and does not guarantee
  that every member is scientifically coherent.
- Raising the height merges groups. That hierarchy property is checked, but
  human abstract review is still needed to assess semantic quality.

## Suggested 8–10 minute demonstration

1. Explain the problem and data coverage, including the partial-year caveat.
2. Search CO2 capture and show the keyword list at height 1.00.
3. Switch between One keyword and Whole theme to explain the difference.
4. Move to 0.75 and 1.25 and explain a concrete split or merge.
5. Show the trend, map, institute list and supporting-paper links.
6. Present the three priority analysis questions and the validation approach.

## Validation and limits to state

The map and trend count **keyword mentions**; institute rankings count
**distinct papers**. Several institutes can receive credit for one paper.
Country spelling aliases are summed, and explicit map codes prevent guessed
locations. Map countries still come from the original keyword extraction;
they have not all been independently geocoded from affiliations.

Institute attribution joins original records by year, file and exact title.
Both the recorded `title` and `topic` fields are accepted as exact paper-title
aliases. This recovers 2019's numbered presentation titles without fuzzy matching.
Missing or ambiguous matches, failed-scrape placeholder titles, phone/email
contact fields and wrong-year source records are excluded. Department/campus
names and spelling variants may remain separate; the names are not a fully
curated institutional registry.

Automated checks validate every keyword assignment, counts, country/year
rollups, hierarchy nesting and institute source trail. These establish
consistency with stored records. They cannot prove that every upstream scrape,
AI-extracted keyword or clustering decision is correct. Record that distinction
as part of the research method, and propose expert review as the next step.

The new snapshot's source preflight has already passed for 383,742
institute/keyword/paper links, 29,599 matched papers and 263,326 keyword/paper
pairs. The full clustering/index checks will run after Ward finishes; do not
present those as completed until the refresh status says complete.

## Refresh status

The completion job will build all five heights, rebuild country and institute
indices, run the full data and Streamlit checks, and only then replace the
local website snapshot. A copy of the old dataset is retained for recovery.

See `keyword_refresh_2026-10-13/refresh_status.json` for current status and
`keyword_refresh_2026-10-13/snapshot_summary.json` for frozen source counts.
Files completed by the running 2021 extraction after the snapshot are outside
this refresh and need a later rebuild. Its input directory currently also
contains 2022 chunks; correct that mixture before using its folder name alone
to assign years in a subsequent extraction/aggregation run.

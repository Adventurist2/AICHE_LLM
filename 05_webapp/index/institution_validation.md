# Institute validation

All checks passed against the saved original conference scrape and keyword aggregate.

- 383,742 institute/keyword/paper links audited.
- 29,599 matched papers; 7,440 recorded institute/affiliation names.
- All 263,326 keyword/paper pairs independently matched by year, source file and exact title.
- Every original affiliation occurs in the source author fields; every shortened institute name is supported by an entire comma-delimited source name.
- Duplicate links, cross-year matches and unsupported contact values are absent.
- 357,019 exported institute/keyword pairs match distinct-paper counts.
- 5 invalid contact affiliation records excluded; see institution_excluded_affiliations.csv.

## CO2 capture, whole theme, threshold 1.00

28 keywords; 287 matched papers; 280 with valid affiliations; 239 institute/affiliation names.

| Institute / affiliation | Distinct papers |
|---|---:|
| Georgia Institute of Technology | 17 |
| The Ohio State University | 14 |
| National Energy Technology Laboratory | 12 |
| Khalifa University | 11 |
| Columbia University | 9 |
| National University of Singapore | 8 |
| University of Alberta | 8 |
| Imperial College London | 7 |
| West Virginia University | 7 |
| Korea Institute of Energy Research | 6 |
| University of Southern California | 6 |
| University of Ottawa | 5 |

The full source trail is in institution_validation_evidence.csv, including original affiliation text, paper titles, years, URLs and source files.

## Limits

This validates attribution to the stored conference records, not an independently curated institution registry. Original scrape errors and keyword extraction errors can remain. Department/location strings and spelling variants may remain separate. A whole theme includes related cluster keywords; use One keyword for exact-keyword attribution. Missing or ambiguous paper matches are excluded, and affiliations are not inferred.

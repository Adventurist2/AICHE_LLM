"""Reading guide for the metrics actually displayed by the Atlas."""
import pandas as pd
import streamlit as st


def render_about(ctx):
    st.title('About & metrics')
    st.caption('What the numbers mean, how to read the figures, and where the evidence stops.')
    metrics, graphs, methods = st.tabs(['Metric definitions', 'Reading the graphs', 'Methods & coverage'])
    with metrics:
        st.markdown('''### Two units, two different questions
**Mentions** measure how often keywords occur in the processed extraction records.
**Distinct papers** measure how many different matched source papers support a result.

If one paper contributes “CO2 capture” and “carbon dioxide separation” to the same
theme, it contributes **two theme mentions** but **one paper** to an institute’s count.
Repeated extraction listings can also contribute mentions; institute counts deduplicate source papers.
''')
        definitions = [
            ('Keywords', 'Distinct canonical keyword strings in the dataset.', 'Vocabulary coverage, not the number of papers or independent ideas.'),
            ('Themes', 'Clusters at the current Ward cut height.', 'Research groupings at this level of detail; increasing the height merges themes.'),
            ('Meeting years', 'Years represented in this snapshot.', 'Temporal coverage; missing years and partial extractions are not evidence of zero activity.'),
            ('Keyword / theme mentions', 'Sum of extracted keyword occurrences for the chosen term or all theme members.', 'Observed attention in these records; not unique papers, citations, impact or a normalized growth rate.'),
            ('Keywords in theme', 'Number of distinct member strings in the selected cluster.', 'Cluster breadth. This remains a theme-level value even in One keyword mode.'),
            ('Mapped countries', 'Distinct reported country names with an unambiguous map code in the selection.', 'Geographic spread; this is a country count, not a paper count.'),
            ('Papers with affiliations', 'Distinct matched papers in the selection with at least one usable recorded affiliation.', 'Source-backed affiliation coverage. Unmatched or missing affiliations are excluded.'),
        ]
        for metric, calculation, significance in definitions:
            with st.expander(metric, expanded=metric == 'Keyword / theme mentions'):
                st.markdown(f'**How it is calculated:** {calculation}\n\n**Why it matters:** {significance}')
        with st.expander('Institute table columns and coverage ratios'):
            st.markdown('''**Papers:** distinct papers credited to an institute. Multiple authors at that institute count once.
A paper with two institutes can count once for each, so summing institute rows can exceed the number of unique papers.

**Keywords / keyword list:** distinct terms connecting that institute to the selection.
**Years:** meeting years represented by those supporting papers.

**Affiliation coverage:** papers with usable affiliations ÷ matched papers for the selection.
For example, 80 out of 100 means 80% coverage among matched papers, not 80% of the full conference.
Source-file/title coverage tables count references before duplicate papers are combined.
''')
    with graphs:
        st.markdown('''### Research over time — line chart
The horizontal axis is the meeting year; the vertical axis is keyword mentions for
the selected term or theme. Higher points show more occurrences in processed records.
Use the chart to locate active years and inspect supporting themes. Larger meetings,
duplicate listings or better extraction coverage can also raise the line. A rise alone
does **not** prove growth in the wider research field. Missing years are unobserved,
not zero; connecting lines do not represent measurements between meetings.

### Around the world — map
Darker countries have more mentions attributed to their reported names. The color
legend shows the number of mentions, and the country table provides exact values.
Use it to explore the observed geographic footprint. A neutral country has no mapped
value in this selection; that does not establish absence of research. Color scales can
change with the selection, so compare actual values rather than shades across maps.
Country assignments come from extraction records, not independent affiliation geocoding.

### Trends and geography — ranked bars
Bar length is keyword mentions for a theme in the chosen meeting year or country.
The longest bar ranks highest by this count within the current snapshot and threshold.
Top N limits the displayed rows; omitted themes still exist. These charts show observed
prominence, not quality, citations, funding or a country’s research productivity.

### Institute keywords and theme tables
These connect research terms to distinct supporting papers and recorded affiliations.
Use them to investigate participation and possible specialization, then inspect the paper
links. Raw paper totals alone do not establish comparative institutional strength.
''')
    with methods:
        st.markdown('''### Selection and clustering
**Whole theme** includes every keyword in the selected cluster. **One keyword** uses
only the selected term’s counts. An institute may appear for a related member keyword
in Whole theme even when it does not have the exact search term.

Keywords use 384-dimensional all-MiniLM-L6-v2 sentence embeddings. Ward hierarchical
clustering groups the full-dimensional embeddings in one tree across years.
The height slider cuts that tree: lower heights create narrower groups; higher heights
merge them into broader themes. **0.75 is a Ward distance, not 75% similarity or confidence.**
Labels are representative member keywords, with labels reused only for identical groups.
Semantic grouping is an exploratory aid and still benefits from expert review.

### Attribution and validation
Country spelling aliases are summed and mapped through explicit codes. Ambiguous
locations remain in the country table without a guessed map position. One record can
credit several countries, so country counts need not sum to the total mention count.

Institutes are joined through the same year, source file and exact recorded title/topic.
Paper URLs deduplicate repeated listings. Missing or ambiguous matches and invalid
contact fields are excluded. Department, campus and spelling variants can remain separate;
this is a recorded affiliation list, not a fully curated institution registry.

Checks validate assignments, year/country rollups, hierarchy nesting, displayed counts
and affiliation provenance. They establish consistency with saved records, not a guarantee
that every scrape, AI-extracted keyword or semantic cluster is correct.
''')
        if ctx and ctx.get('coverage_data'):
            coverage = ctx['coverage_data']
            st.subheader('Extraction coverage')
            st.caption(f"Snapshot · {coverage['snapshot_date']}")
            partial = coverage.get('partial_years', [])
            if partial:
                st.info('Partial extraction: ' + ', '.join(map(str, partial)) + '. Avoid treating lower counts as a research decline.')
            frame = pd.DataFrame.from_dict(coverage['extraction_records_by_year'], orient='index')
            st.dataframe(frame.rename_axis('Year').reset_index().rename(columns={
                'files': 'Extraction files', 'records': 'Processed records', 'with_keywords': 'Records with keywords'}),
                hide_index=True, width='stretch', height=300)
        else:
            st.info('A detailed extraction-coverage snapshot is not available for this dataset.')
        st.markdown('''### Fair comparisons
Year, country and institute coverage differs. For research comparisons, examine
distinct-paper shares with a clearly stated denominator and minimum sample size,
review name variants, and separate incomplete years. Those normalized comparisons
are not what the current raw-count plots display.
''')

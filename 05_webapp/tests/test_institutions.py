import json
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from institutions import AffiliationNames, affiliations, build_institutions, institute_summary, keyword_summary


class InstitutionTests(unittest.TestCase):
    def test_contact_values_are_not_institutes(self):
        paper = dict(authors_structured=[dict(affiliation=value) for value in (
            '1234567890', '+1 (234) 567-8900', 'person@example.test',
            'person@example.test, Town, Country', 'Unknown', '3M',
            'CNRS@CREATE', 'SUNY @ Buffalo', 'Alpha University')])
        self.assertEqual(affiliations(paper), {'3M', 'CNRS@CREATE', 'SUNY @ Buffalo', 'Alpha University'})

    def test_exact_affiliation_names_keep_campus_and_ambiguity(self):
        names = AffiliationNames(['Alpha University'] * 3 + ['ALPHA UNIVERSITY', 'Beta University',
            'University of California', 'University of California, Berkeley'])
        self.assertEqual(names.resolve('Chemical Engineering, Alpha University, Boston, MA'), 'Alpha University')
        self.assertEqual(names.resolve('University of California, Berkeley, Berkeley, CA'),
                         'University of California, Berkeley')
        self.assertEqual(names.resolve('University of California, Davis, Davis, CA'),
                         'University of California, Davis, Davis, CA')
        ambiguous = 'Alpha University, Beta University'
        self.assertEqual(names.resolve(ambiguous), ambiguous)
        self.assertEqual(names.resolve('Alpha University Downtown'), 'Alpha University Downtown')
        units = AffiliationNames(['Chemical Engineering', 'Singapore', 'Alpha University'])
        self.assertEqual(units.resolve('Chemical Engineering, Unrecognized Organization, Singapore'),
                         'Chemical Engineering, Unrecognized Organization, Singapore')

    def test_source_scoped_links_deduplicate_papers_not_keywords(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            def paper(title, url, affiliations):
                return dict(title=title, topic=title, url=url,
                            authors_structured=[dict(affiliation=a) for a in affiliations])
            (raw / 'session1.json').write_text(json.dumps([
                paper('Error Scraping', 'https://example.test/Paper/1', []),
                dict(paper('Capture', 'https://example.test/Paper/1', ['Alpha University', 'Alpha University']),
                     topic='10a- Capture'),
                paper('Capture', 'https://example.test/wrong.pdf', ['Wrong University']),
                paper('Capture', 'https://aiche.confex.com/aiche/2022/meetingapp.cgi/Paper/1', ['Wrong Year University']),
                paper('No affiliation', 'https://example.test/Paper/2', []),
                paper('Ambiguous', 'https://example.test/Paper/3', ['Alpha University']),
                paper('Ambiguous', 'https://example.test/Paper/4', ['Beta University']),
            ]), encoding='utf-8')
            (raw / 'session2.json').write_text(json.dumps([
                paper('Capture', 'https://example.test/Paper/1', ['Alpha University']),
                paper('Unrelated', 'https://example.test/Paper/5', ['Beta University']),
            ]), encoding='utf-8')
            def ref(title, file):
                return dict(title=title, source_file=file, source_folder='groq/extracted_results_2024')
            aggregate = {
                'capture': {'papers_by_year': {'2024': [ref('Capture', 'ext_session1_p1.json'),
                    ref('Capture', 'ext_session2_p1.json'), ref('No affiliation', 'ext_session1_p1.json'),
                    ref('Ambiguous', 'ext_session1_p1.json'), ref('Unrelated', 'ext_session1_p1.json')] }},
                'storage': {'papers_by_year': {'2024': [ref('10a- Capture', 'ext_session1_p1.json')] }},
            }
            source = root / 'aggregate.json'
            source.write_text(json.dumps(aggregate), encoding='utf-8')
            out = root / 'index'
            meta = build_institutions(source, out, {'2024': ['raw']}, root)
            self.assertEqual(meta['matched_papers'], 2)
            self.assertEqual(meta['papers_with_affiliations'], 1)
            self.assertEqual(meta['coverage_by_year']['2024']['ambiguous_title'], 1)
            self.assertEqual(meta['coverage_by_year']['2024']['source_or_title_not_found'], 1)
            links = pd.read_parquet(out / 'institution_links.parquet')
            self.assertEqual(set(links.institute), {'Alpha University'})
            summary = institute_summary(links)
            self.assertEqual(summary.iloc[0]['Papers'], 1)
            self.assertEqual(summary.iloc[0]['Keywords'], 2)
            self.assertEqual(keyword_summary(links, 'Alpha University').Papers.tolist(), [1, 1])
            self.assertEqual(len(pd.read_csv(out / 'institute_keywords.csv')), 2)
            self.assertEqual(len(pd.read_parquet(out / 'paper_keywords.parquet')), 3)
            self.assertEqual(set(pd.read_parquet(out / 'institution_papers.parquet').title),
                             {'Capture', 'No affiliation'})


if __name__ == '__main__':
    unittest.main()

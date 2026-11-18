"""Adding cut heights reuses the tree; changing source counts refreshes outputs."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


class TreeCacheTests(unittest.TestCase):
    def test_new_heights_reuse_tree_and_source_changes_refresh(self):
        path = Path(__file__).resolve().parents[2] / '04_clustering' / 'cluster_keywords.py'
        spec = importlib.util.spec_from_file_location('test_cluster_pipeline', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'aggregate.json'
            data = {kw: {'total_count': 1, 'years': {'2023': 1}, 'countries': {'USA': 1}}
                    for kw in ('a', 'b', 'c')}
            source.write_text(json.dumps(data), encoding='utf-8')
            output = root / 'results'
            with patch.object(module, 'SentenceTransformer', return_value=object()), patch.object(
                    module, 'EmbeddingCache') as cache, patch.object(
                    module, 'build_linkage', wraps=module.build_linkage) as linkage:
                cache.return_value.get.return_value = np.array([[1., 0.], [.99, .01], [0., 1.]])
                def run(*heights):
                    args = ['cluster_keywords.py', str(source), '--no-llm', '--output-dir', str(output),
                            '--thresholds', *map(str, heights)]
                    with patch.object(sys, 'argv', args):
                        module.main()
                run(0.5)
                run(0.5, 0.75, 1.25)
                self.assertEqual(linkage.call_count, 1)
                for height in (0.5, 0.75, 1.25):
                    result = json.loads((output / f'clusters_dt{height}.json').read_text())
                    self.assertEqual(sum(c['total_count'] for c in result['clusters'].values()), 3)
                data['a']['total_count'] = 4
                data['a']['years']['2023'] = 4
                data['a']['countries']['USA'] = 4
                source.write_text(json.dumps(data), encoding='utf-8')
                run(0.75)
                self.assertEqual(linkage.call_count, 2)
                result = json.loads((output / 'clusters_dt0.75.json').read_text())
                self.assertEqual(sum(c['total_count'] for c in result['clusters'].values()), 6)

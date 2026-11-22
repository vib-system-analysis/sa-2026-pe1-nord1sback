import csv
import tempfile
import unittest
from pathlib import Path
import analyze


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.g, self.nodes, self.edges = analyze.load_graph()

    def test_original(self):
        r = analyze.summary(self.g)
        self.assertEqual((r['vertices'], r['arcs']), (10, 17))
        self.assertEqual((len(r['weak_components']), len(r['strong_components'])), (1, 5))
        self.assertEqual(r['degrees']['F'], {'in': 5, 'out': 4, 'total': 9})
        self.assertEqual(analyze.shortest(self.g, 'G', 'D'), ['G', 'S', 'F', 'D'])

    def test_failure(self):
        r = analyze.summary(analyze.without(self.g, 'F'))
        self.assertEqual((r['vertices'], r['arcs']), (9, 8))
        self.assertEqual({frozenset(c) for c in r['weak_components']}, {frozenset('DEGSTUW'), frozenset('H'), frozenset('M')})
        self.assertEqual(len(r['strong_components']), 8)
        self.assertIsNone(r['paths']['G']['D'])
        self.assertFalse(r['main_circuit_available'])
        u = analyze.summary(analyze.without(self.g, 'U'))
        self.assertIsNotNone(u['paths']['G']['D'])
        self.assertFalse(u['main_circuit_available'])
        for node in ('H', 'M'):
            self.assertTrue(analyze.summary(analyze.without(self.g, node))['main_circuit_available'])

    def test_extension_and_inconsistency(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name in ('nodes.csv', 'edges.csv', 'adjacency.csv'):
                (p / name).write_bytes((analyze.ROOT / name).read_bytes())
            with (p / 'nodes.csv').open('a', encoding='utf-8', newline='') as f:
                csv.writer(f).writerow(['X', 'new', 'test'])
            with (p / 'adjacency.csv').open(encoding='utf-8', newline='') as f:
                rows = list(csv.reader(f))
            rows[0].append('X')
            for row in rows[1:]:
                row.append('1' if row[0] == 'D' else '0')
            rows.append(['X'] + ['0'] * 11)
            with (p / 'adjacency.csv').open('w', encoding='utf-8', newline='') as f:
                csv.writer(f).writerows(rows)
            with self.assertRaises(ValueError):
                analyze.load_graph(p)
            with (p / 'edges.csv').open('a', encoding='utf-8', newline='') as f:
                csv.writer(f).writerow(['E18', 'D', 'X', 'данные', 'test'])
            graph, _, edges = analyze.load_graph(p)
            self.assertEqual(analyze.shortest(graph, 'G', 'X'), ['G', 'S', 'F', 'D', 'X'])
            self.assertEqual(analyze.summary(graph)['arcs'], 18)
            analyze.svg(p / 'graph.svg', graph, edges)
            self.assertIn('E18', (p / 'graph.svg').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()

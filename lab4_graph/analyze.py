"""Recalculate graph reports from the CSV inputs using only Python's standard library."""
import csv
import html
import json
import math
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_graph(root=ROOT):
    with (root / 'nodes.csv').open(encoding='utf-8', newline='') as f:
        nodes = list(csv.DictReader(f))
    ids = [n['id'] for n in nodes]
    if not ids or len(ids) != len(set(ids)) or any(not i for i in ids):
        raise ValueError('Node identifiers must be nonempty and unique')
    with (root / 'adjacency.csv').open(encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] != ['id'] + ids or len(rows) != len(ids) + 1:
        raise ValueError('Matrix header or size does not match nodes')
    if any(len(row) != len(ids) + 1 for row in rows[1:]) or [r[0] for r in rows[1:]] != ids:
        raise ValueError('Matrix rows do not match nodes')
    if any(v not in ('0', '1') for row in rows[1:] for v in row[1:]):
        raise ValueError('Matrix values must be 0 or 1')
    graph = {row[0]: [ids[i] for i, v in enumerate(row[1:]) if v == '1'] for row in rows[1:]}
    with (root / 'edges.csv').open(encoding='utf-8', newline='') as f:
        edges = list(csv.DictReader(f))
    pairs = [(e['source'], e['target']) for e in edges]
    if len({e['id'] for e in edges}) != len(edges) or len(set(pairs)) != len(pairs):
        raise ValueError('Duplicate edge identifier or pair')
    if set(pairs) != {(u, v) for u in ids for v in graph[u]}:
        raise ValueError('Edge catalogue and adjacency matrix differ')
    return graph, nodes, edges


def shortest(graph, start, end):
    if start not in graph or end not in graph:
        return None
    queue = deque([[start]])
    seen = {start}
    while queue:
        path = queue.popleft()
        if path[-1] == end:
            return path
        for v in graph[path[-1]]:
            if v not in seen:
                seen.add(v)
                queue.append(path + [v])
    return None


def components(graph, strong=False):
    remaining = set(graph)
    groups = []
    while remaining:
        u = next(v for v in graph if v in remaining)
        if strong:
            group = {v for v in remaining if shortest(graph, u, v) and shortest(graph, v, u)}
        else:
            group, queue = {u}, deque([u])
            while queue:
                x = queue.popleft()
                neighbors = set(graph[x]) | {v for v in graph if x in graph[v]}
                for v in neighbors - group:
                    group.add(v)
                    queue.append(v)
        remaining -= group
        groups.append([v for v in graph if v in group])
    return groups


def without(graph, node):
    return {u: [v for v in vs if v != node] for u, vs in graph.items() if u != node}


def summary(graph):
    degrees = {u: {'in': sum(u in vs for vs in graph.values()), 'out': len(graph[u])} for u in graph}
    for d in degrees.values():
        d['total'] = d['in'] + d['out']
    return {'vertices': len(graph), 'arcs': sum(map(len, graph.values())), 'degrees': degrees,
            'weak_components': components(graph), 'strong_components': components(graph, True),
            'paths': {u: {v: shortest(graph, u, v) for v in graph} for u in graph},
            'main_circuit_available': 'U' in graph and shortest(graph, 'G', 'D') is not None}


def write_matrix(path, graph):
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['id'] + list(graph))
        for u in graph:
            w.writerow([u] + [int(v in graph[u]) for v in graph])


def svg(path, graph, edges):
    ids = list(graph)
    n = len(ids)
    points = {v: (400 + 270 * math.cos(2 * math.pi * i / n - math.pi / 2),
                  350 + 270 * math.sin(2 * math.pi * i / n - math.pi / 2)) for i, v in enumerate(ids)}
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="700" viewBox="0 0 800 700">',
           '<title>Directed graph</title><defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#405268"/></marker></defs>',
           '<rect width="800" height="700" fill="white"/>']
    for e in edges:
        u, v = e['source'], e['target']
        if u not in graph or v not in graph[u]:
            continue
        x1, y1 = points[u]; x2, y2 = points[v]
        dx, dy = x2-x1, y2-y1; length = math.hypot(dx, dy)
        if not length:  # self-loops remain visible when the graph grows
            out.append(f'<path d="M {x1-12:.1f} {y1-17:.1f} C {x1-55:.1f} {y1-80:.1f}, {x1+55:.1f} {y1-80:.1f}, {x1+12:.1f} {y1-17:.1f}" fill="none" stroke="#405268" marker-end="url(#a)"/>')
            continue
        ux, uy = dx/length, dy/length
        # Offset reciprocal arcs so both directions remain visible.
        offset = 8 if u in graph[v] else 0
        px, py = -uy*offset, ux*offset
        out.append(f'<line x1="{x1+ux*23+px:.1f}" y1="{y1+uy*23+py:.1f}" x2="{x2-ux*25+px:.1f}" y2="{y2-uy*25+py:.1f}" stroke="#405268" marker-end="url(#a)"/>')
        out.append(f'<text x="{(x1+x2)/2+px:.1f}" y="{(y1+y2)/2+py-4:.1f}" font-size="11" fill="#27364a">{html.escape(e["id"])}</text>')
    for v, (x, y) in points.items():
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="22" fill="#e5f1ff" stroke="#174e80"/><text x="{x:.1f}" y="{y+5:.1f}" text-anchor="middle" font-family="sans-serif" font-size="16">{html.escape(v)}</text>')
    out.append('</svg>')
    path.write_text('\n'.join(out) + '\n', encoding='utf-8')


def main():
    graph, nodes, edges = load_graph()
    result = ROOT / 'results'
    result.mkdir(exist_ok=True)
    reduced = without(graph, 'F')
    report = {'original': summary(graph), 'without_F': summary(reduced),
              'removals': {u: summary(without(graph, u)) for u in graph}}
    (result / 'analysis.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_matrix(result / 'adjacency_without_F.csv', reduced)
    svg(result / 'graph.svg', graph, edges)
    svg(result / 'graph_without_F.svg', reduced, edges)
    print(f"Original: {report['original']['vertices']} vertices, {report['original']['arcs']} arcs")
    print(f"Without F: {report['without_F']['vertices']} vertices, {report['without_F']['arcs']} arcs")


if __name__ == '__main__':
    main()

"""Offline check of test_roads.py's map line helpers (no Overpass, no pmtiles):
python3 scripts/test_roads_check.py"""
import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_roads as tr  # noqa: E402


def way(wid, pts):
    return {'type': 'way', 'id': wid, 'geometry': [{'lat': a, 'lon': b} for a, b in pts]}


def wiggle(lat0, lon0, lat1, n):
    """A winding road going north: n points, a sine of ~150 m across."""
    return [(lat0 + (lat1 - lat0) * k / (n - 1), lon0 + 0.0015 * math.sin(k / 6)) for k in range(n)]


def check():
    road = wiggle(31.70, 35.10, 31.80, 600)  # ~11 km, dense
    # a fake Overpass answer: the road cut into 4 ways, the 2nd one reversed and listed last,
    # a way that goes far out of the bbox, and the other carriageway (a short parallel piece)
    ways = [
        way(1, road[0:150]),
        way(3, road[300:450]),
        way(4, road[449:] + [(31.95, 35.10)]),  # leaves the bbox far to the north
        way(2, road[149:301][::-1]),
        way(5, [(p[0], p[1] + 0.0002) for p in road[200:260]]),  # the other carriageway
    ]
    bbox = [35.09, 31.69, 35.12, 31.81]

    # clip: the point far outside is dropped
    assert all(p[0] < 31.82 for w in ways for run in tr.clip(w['geometry'], bbox) for p in run)
    # a way leaving and coming back is two runs
    assert len(tr.clip([{'lat': 31.7, 'lon': 35.1}, {'lat': 31.71, 'lon': 35.1}, {'lat': 32.5, 'lon': 35.1},
                        {'lat': 31.72, 'lon': 35.1}, {'lat': 31.73, 'lon': 35.1}], bbox)) == 2

    # chaining: one line, end to end, the carriageway not added
    pieces = [run for w in ways for run in tr.clip(w['geometry'], bbox)]
    line = tr.chain(pieces)
    ends = sorted([line[0], line[-1]])
    assert ends[0] == road[0] and ends[1] == road[-1], ends
    assert abs(tr.length_m(line) - tr.length_m(road)) < 1, (tr.length_m(line), tr.length_m(road))

    # a piece with a gap (no shared node) is joined when close, not when far
    a, b = road[:100], road[102:200]
    assert len(tr.chain([a, b])) == len(a) + len(b)
    far = [(p[0] + 0.05, p[1]) for p in road[:50]]
    assert len(tr.chain([a, far])) == len(a)

    # simplify: few points, still within 20 m of every original point, ends kept
    s = tr.simplify(line)
    assert s[0] == line[0] and s[-1] == line[-1]
    assert len(s) < len(line) / 3, len(s)
    assert max(min(dist_to_segment(p, x, y) for x, y in zip(s, s[1:])) for p in line) <= 20.5
    # never more than MAX_POINTS
    zigzag = [(31.7 + k * 0.0001, 35.1 + (0.001 if k % 2 else 0)) for k in range(3000)]
    assert len(tr.simplify(zigzag)) <= tr.MAX_POINTS

    # the manifest entry of a recommended road: line, ends; others unchanged
    r = {'id': 'rec-1', 'name_he': 'א', 'name_en': 'A', 'bbox': bbox, 'ref': '^1$', 'recommended': True, 'curves': 7, 'length_km': 11.1}
    e = tr.entry_for(r, ways)
    assert e['recommended'] is True and e['curves'] == 7 and e['length_km'] == 11.1 and e['ways'] == 5
    assert 2 < len(e['line']) <= tr.MAX_POINTS
    assert e['ends'] == [e['line'][0], e['line'][-1]]
    assert sorted(e['ends']) == sorted([[round(road[0][0], 5), round(road[0][1], 5)], [round(road[-1][0], 5), round(road[-1][1], 5)]])
    plain = tr.entry_for({k: v for k, v in r.items() if k not in ('recommended', 'curves', 'length_km')}, ways)
    assert set(plain) == {'id', 'name_he', 'name_en', 'bbox', 'ways', 'km'}, plain.keys()
    none = tr.entry_for(r, [])
    assert none['ways'] == 0 and 'line' not in none and none['recommended'] is True
    print(f'ok: {len(line)} points chained, {len(s)} after simplify, {len(e["line"])} in the manifest')


def dist_to_segment(p, a, b):
    lat0 = math.radians(a[0])
    xy = lambda q: ((q[1] - a[1]) * math.cos(lat0) * 111195.0, (q[0] - a[0]) * 111195.0)
    (x, y), (x1, y1), (x2, y2) = xy(p), xy(a), xy(b)
    dx, dy = x2 - x1, y2 - y1
    d2 = dx * dx + dy * dy
    t = 0 if d2 == 0 else max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / d2))
    return math.hypot(x - x1 - t * dx, y - y1 - t * dy)


if __name__ == '__main__':
    check()

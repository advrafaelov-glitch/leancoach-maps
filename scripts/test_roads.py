"""Builds the test roads into out-test/: for each road of test-roads.json, its OSM ways
(roads with the given ref - or name, when given - inside the bbox) as <id>.kml, a small map picture <id>.pmtiles
(the bbox, from the Protomaps build), and test-roads.json (what the app reads: names,
bbox, files, sizes, md5, ways and km found). A road with no ways is listed with
"ways": 0 and no files, so a wrong ref or bbox shows in the manifest.

Recommended roads (3.11.2026, "recommended": true - a list for riders in both apps) also
carry what the ride screen's map draws: "line" (the ways inside the bbox chained into one
line and simplified, [[lat, lon], ...], a few hundred points at most) and "ends" (its two
far ends, where navigation takes the rider). "curves" and "length_km" of a road part come
from test-roads.json as they are (the road analysis of 2.11.2026).
usage: test_roads.py <protomaps-build>   (needs: pmtiles, network)
check: python3 scripts/test_roads_check.py   (offline: the line / ends helpers)"""
import hashlib, json, math, os, subprocess, sys, time, urllib.parse, urllib.request

OUT = 'out-test'
OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
UA = 'LeanCoach-test-roads (github.com/advrafaelov-glitch/leancoach-maps)'

# the map line of a recommended road
SIMPLIFY_M = 20.0      # Douglas-Peucker tolerance
MAX_POINTS = 400       # more points: the tolerance grows until it fits
CLIP_PAD = 0.002       # degrees around the bbox kept when cutting long ways
JOIN_M = 1000.0        # pieces of the road further apart than this are not joined
EXTEND_M = 200.0       # a piece must take the line at least this much further (not the other carriageway)


def overpass(q):
    for attempt in range(6):
        url = OVERPASS[attempt % len(OVERPASS)]
        try:
            req = urllib.request.Request(url, data=urllib.parse.urlencode({'data': q}).encode(), headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except Exception as e:  # busy server: wait and try the other one
            print(f'  overpass {url}: {e}', flush=True)
            time.sleep(20 * (attempt + 1))
    raise RuntimeError('Overpass not reachable')


def km(geom):
    t = 0.0
    for a, b in zip(geom, geom[1:]):
        la = math.radians((a['lat'] + b['lat']) / 2)
        t += math.hypot((b['lon'] - a['lon']) * math.cos(la), b['lat'] - a['lat']) * 111.195
    return t


# ---------------------------------------------------------------- the map line
def metres(a, b):
    """Distance in metres between two (lat, lon) points (flat earth: short distances)."""
    la = math.radians((a[0] + b[0]) / 2)
    return math.hypot((b[1] - a[1]) * math.cos(la), b[0] - a[0]) * 111195.0


def length_m(line):
    return sum(metres(a, b) for a, b in zip(line, line[1:]))


def clip(geom, bbox, pad=CLIP_PAD):
    """The runs of a way's points inside the bbox (grown by `pad`): Overpass gives whole
    ways, and a long way may go far outside the road part."""
    w, s, e, n = bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad
    runs, run = [], []
    for g in geom:
        p = (g['lat'], g['lon'])
        if w <= p[1] <= e and s <= p[0] <= n:
            run.append(p)
        else:
            if len(run) > 1:
                runs.append(run)
            run = []
    if len(run) > 1:
        runs.append(run)
    return runs


def join_shared(pieces):
    """Joins pieces that share an end node (OSM ways of one road meet at a node)."""
    pieces = [list(p) for p in pieces if len(p) > 1]
    joined = True
    while joined:
        joined = False
        for i in range(len(pieces)):
            for j in range(i + 1, len(pieces)):
                a, b = pieces[i], pieces[j]
                if a[-1] == b[0]:
                    m = a + b[1:]
                elif a[-1] == b[-1]:
                    m = a + b[::-1][1:]
                elif a[0] == b[-1]:
                    m = b + a[1:]
                elif a[0] == b[0]:
                    m = b[::-1] + a[1:]
                else:
                    continue
                pieces[i] = m
                del pieces[j]
                joined = True
                break
            if joined:
                break
    return pieces


def chain(pieces, join_m=JOIN_M, extend_m=EXTEND_M):
    """One line from the pieces: the longest, then the nearest piece at either end while it
    is close (`join_m`) and takes the line further away (the other carriageway of a dual
    road, or a branch back, does not)."""
    pieces = join_shared(pieces)
    if not pieces:
        return []
    pieces.sort(key=length_m, reverse=True)
    line = pieces.pop(0)
    while pieces:
        best = None
        for k, p in enumerate(pieces):
            for at_end in (True, False):
                tip, other = (line[-1], line[0]) if at_end else (line[0], line[-1])
                for flip in (False, True):
                    q = p[::-1] if flip else p
                    gap = metres(tip, q[0])
                    if gap > join_m or metres(q[-1], other) < metres(tip, other) + extend_m:
                        continue
                    if best is None or gap < best[0]:
                        best = (gap, k, at_end, q)
        if best is None:
            break
        _, k, at_end, q = best
        line = line + q if at_end else q[::-1] + line
        del pieces[k]
    return line


def _dp(points, tol):
    # in metres around the first point
    lat0 = math.radians(points[0][0])
    xy = [((p[1] - points[0][1]) * math.cos(lat0) * 111195.0, (p[0] - points[0][0]) * 111195.0) for p in points]
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        (x1, y1), (x2, y2) = xy[i], xy[j]
        dx, dy = x2 - x1, y2 - y1
        d2 = dx * dx + dy * dy
        far, far_k = 0.0, -1
        for k in range(i + 1, j):
            x, y = xy[k]
            if d2 == 0:
                d = math.hypot(x - x1, y - y1)
            else:
                t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / d2))
                d = math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))
            if d > far:
                far, far_k = d, k
        if far > tol and far_k > 0:
            keep[far_k] = True
            stack += [(i, far_k), (far_k, j)]
    return [p for p, k in zip(points, keep) if k]


def simplify(points, tol_m=SIMPLIFY_M, max_points=MAX_POINTS):
    """Douglas-Peucker in metres; the tolerance grows until at most `max_points` stay."""
    if len(points) < 3:
        return list(points)
    tol = tol_m
    out = _dp(points, tol)
    while len(out) > max_points:
        tol *= 1.5
        out = _dp(points, tol)
    return out


def road_line(ways, bbox):
    """The recommended road's map line, [[lat, lon], ...] (5 decimals: about 1 m)."""
    pieces = [run for x in ways for run in clip(x['geometry'], bbox)]
    line = simplify(chain(pieces))
    return [[round(p[0], 5), round(p[1], 5)] for p in line]


def far_ends(line):
    """The two ends of the road part (where the rider starts or finishes it)."""
    return [list(line[0]), list(line[-1])] if len(line) > 1 else []


def entry_for(r, ways):
    """What the manifest says of a road (without its files)."""
    entry = {k: r[k] for k in ('id', 'name_he', 'name_en', 'bbox')}
    entry['ways'] = len(ways)
    entry['km'] = round(sum(km(x['geometry']) for x in ways), 1)
    for k in ('curves', 'length_km'):
        if k in r:
            entry[k] = r[k]
    if r.get('recommended'):
        entry['recommended'] = True
        line = road_line(ways, r['bbox']) if ways else []
        if len(line) > 1:
            entry['line'] = line
            entry['ends'] = far_ends(line)
    return entry


# ---------------------------------------------------------------- the build
def info(name):
    p = os.path.join(OUT, name)
    data = open(p, 'rb').read()
    return {'file': name, 'bytes': len(data), 'md5': hashlib.md5(data).hexdigest()}


def main(build):
    os.makedirs(OUT, exist_ok=True)
    roads = json.load(open('test-roads.json', encoding='utf-8'))['roads']
    listed = []
    for r in roads:
        w, s, e, n = r['bbox']
        by_name = f'way["highway"]["name"~"{r["name"]}"]({s},{w},{n},{e});' if r.get('name') else ''
        q = f'[out:json][timeout:120];(way["highway"]["ref"~"{r["ref"]}"]({s},{w},{n},{e});{by_name});out geom;'
        print(f"{r['id']}: {q}", flush=True)
        error = None
        try:
            ways = [x for x in overpass(q).get('elements', []) if x.get('type') == 'way' and x.get('geometry')]
        except Exception as e:  # one road failing must not stop the others
            print(f'  failed: {e}', flush=True)
            error = str(e)
            ways = []
        entry = entry_for(r, ways)
        if error:
            entry['error'] = error
        print(f"  {len(ways)} ways, {entry['km']} km" + (f", line {len(entry.get('line', []))} points" if r.get('recommended') else ''), flush=True)
        if ways:
            marks = ''.join(
                '<Placemark><name>%s</name><LineString><coordinates>%s</coordinates></LineString></Placemark>' % (
                    x['id'], ' '.join(f"{g['lon']:.7f},{g['lat']:.7f},0" for g in x['geometry']))
                for x in ways)
            open(os.path.join(OUT, f"{r['id']}.kml"), 'w', encoding='utf-8').write(
                f'<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>{r["name_en"]}</name>{marks}</Document></kml>')
            entry['track'] = info(f"{r['id']}.kml")
            pad = 0.01
            subprocess.run(['pmtiles', 'extract', f'https://build.protomaps.com/{build}.pmtiles', os.path.join(OUT, f"{r['id']}.pmtiles"),
                            f'--bbox={w - pad},{s - pad},{e + pad},{n + pad}', '--maxzoom=15'], check=True)
            entry['tiles'] = info(f"{r['id']}.pmtiles")
        listed.append(entry)
        time.sleep(5)  # be kind to the public Overpass servers

    json.dump({'format': 'leancoach-test-roads', 'version': 1, 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'attribution': '© OpenStreetMap contributors (ODbL) · Protomaps', 'tiles_build': build, 'roads': listed},
              open(os.path.join(OUT, 'test-roads.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(json.dumps([(x['id'], x['ways'], x['km']) for x in listed]))
    # Overpass down for most roads: do not replace a good release with an empty one
    built = sum(1 for x in listed if x['ways'] > 0)
    if built < len(listed) // 2:
        sys.exit(f'only {built} of {len(listed)} roads built - not publishing')


if __name__ == '__main__':
    main(sys.argv[1])

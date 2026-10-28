"""Builds the test roads into out-test/: for each road of test-roads.json, its OSM ways
(roads with the given ref inside the bbox) as <id>.kml, a small map picture <id>.pmtiles
(the bbox, from the Protomaps build), and test-roads.json (what the app reads: names,
bbox, files, sizes, md5, ways and km found). A road with no ways is listed with
"ways": 0 and no files, so a wrong ref or bbox shows in the manifest.
usage: test_roads.py <protomaps-build>   (needs: pmtiles, network)"""
import hashlib, json, math, os, subprocess, sys, time, urllib.parse, urllib.request

OUT = 'out-test'
os.makedirs(OUT, exist_ok=True)
build = sys.argv[1]
roads = json.load(open('test-roads.json', encoding='utf-8'))['roads']
OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
UA = 'LeanCoach-test-roads (github.com/advrafaelov-glitch/leancoach-maps)'


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


def info(name):
    p = os.path.join(OUT, name)
    data = open(p, 'rb').read()
    return {'file': name, 'bytes': len(data), 'md5': hashlib.md5(data).hexdigest()}


listed = []
for r in roads:
    w, s, e, n = r['bbox']
    q = f'[out:json][timeout:120];way["highway"]["ref"~"{r["ref"]}"]({s},{w},{n},{e});out geom;'
    print(f"{r['id']}: {q}", flush=True)
    ways = [x for x in overpass(q).get('elements', []) if x.get('type') == 'way' and x.get('geometry')]
    entry = {k: r[k] for k in ('id', 'name_he', 'name_en', 'bbox')}
    entry['ways'] = len(ways)
    entry['km'] = round(sum(km(x['geometry']) for x in ways), 1)
    print(f"  {len(ways)} ways, {entry['km']} km", flush=True)
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

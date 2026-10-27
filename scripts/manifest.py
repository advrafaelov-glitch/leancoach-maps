"""Writes manifest.json, the file the LeanCoach app reads to list and download regions.
usage: manifest.py <out-dir> <protomaps-build> <osm-date>"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

out, build, osm_date = sys.argv[1], sys.argv[2], sys.argv[3]
maxzoom = int(os.environ.get('MAXZOOM', '14'))
regions = json.load(open('regions.json', encoding='utf-8'))['regions']


def info(name):
    path = os.path.join(out, name)
    h, m = hashlib.sha256(), hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
            m.update(chunk)
    # md5: the phone checks downloads with it (expo-file-system computes md5, not sha256)
    return {'file': name, 'bytes': os.path.getsize(path), 'sha256': h.hexdigest(), 'md5': m.hexdigest()}


now = datetime.now(timezone.utc)
manifest = {
    'format': 'leancoach-maps',
    'version': 1,
    'release': now.strftime('%Y%m%d'),
    'created': now.isoformat(timespec='seconds'),
    'sources': {
        'roads': {'name': 'OpenStreetMap via Geofabrik (israel-and-palestine)', 'date': osm_date or None},
        'tiles': {'name': 'Protomaps basemap daily build', 'build': build, 'maxzoom': maxzoom},
    },
    'attribution': '© OpenStreetMap contributors (ODbL) · Protomaps',
    'style': {'layers': info('layers.json'), 'assets': info('assets.zip'),
              'glyphs': 'fonts/{fontstack}/{range}.pbf', 'sprite': 'sprites/v4/light'},
    'regions': [
        {**{k: r[k] for k in ('id', 'name_he', 'name_en', 'bbox')},
         'roads': info(f"{r['id']}.osm.pbf"), 'tiles': info(f"{r['id']}.pmtiles")}
        for r in regions
    ],
}
print(json.dumps(manifest, ensure_ascii=False, indent=2))

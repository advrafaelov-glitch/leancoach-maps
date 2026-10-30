#!/usr/bin/env bash
# Builds the LeanCoach map regions into out/:
#   <id>.osm.pbf   roads and named places (OpenStreetMap, Geofabrik) – the engine's
#                  search, routing and curves
#   <id>.pmtiles   the map picture (Protomaps basemap, OpenStreetMap) – MapLibre
#   layers.json    map style layers (Protomaps "light", Hebrew labels)
#   layers-dark.json  the same, "dark" (the app follows the phone's light / dark mode)
#   assets.zip     fonts and sprites for the style, so the map works offline
#   manifest.json  what the app reads: regions, files, sizes, sha256
# Needs: osmium-tool, pmtiles, node, jq, curl, zip. Run from the repository root.
set -euo pipefail

OUT=out
WORK=work
mkdir -p "$OUT" "$WORK"
MAXZOOM=${MAXZOOM:-14}
GEOFABRIK=https://download.geofabrik.de/asia/israel-and-palestine-latest.osm.pbf

# --- 1. OpenStreetMap data: one download from Geofabrik per build (their request:
#        phones never download from Geofabrik directly).
if [ ! -s "$WORK/country.osm.pbf" ]; then
  curl -fL --retry 3 -o "$WORK/country.osm.pbf" "$GEOFABRIK"
fi
OSM_DATE=$(osmium fileinfo -g header.option.osmosis_replication_timestamp "$WORK/country.osm.pbf" || true)
echo "OSM data: ${OSM_DATE:-unknown date}"

# Only what the engine reads: roads; places to search for - named points (places,
# tourism, sites, amenities, parks, shops, nature) and named areas (a site drawn as an
# outline, e.g. the Western Wall; malls, parks); town borders (which town a street is in).
osmium tags-filter --overwrite -o "$WORK/roads.osm.pbf" "$WORK/country.osm.pbf" \
  w/highway n/place n/tourism n/amenity n/natural n/historic n/leisure n/shop \
  w/tourism w/historic w/amenity w/leisure w/shop \
  r/admin_level=7,8

# All regions in one pass; complete ways: a road crossing a border is whole in each region,
# and so is a town border (boundary relations completed).
jq '{directory: "'"$OUT"'", extracts: [.regions[] | {output: (.id + ".osm.pbf"), bbox: .bbox}]}' regions.json \
  > "$WORK/extracts.json"
osmium extract --overwrite --strategy smart -S types=multipolygon,boundary -c "$WORK/extracts.json" "$WORK/roads.osm.pbf"

# --- 2. Map picture: cut each region from the latest Protomaps daily build.
BUILD=""
for days in 0 1 2 3 4 5 6 7; do
  d=$(date -u -d "-$days day" +%Y%m%d)
  if curl -fsI "https://build.protomaps.com/$d.pmtiles" > /dev/null; then BUILD=$d; break; fi
done
[ -n "$BUILD" ] || { echo "no Protomaps build found in the last 8 days" >&2; exit 1; }
echo "Protomaps build: $BUILD"
for id in $(jq -r '.regions[].id' regions.json); do
  bbox=$(jq -r --arg id "$id" '.regions[] | select(.id == $id) | .bbox | map(tostring) | join(",")' regions.json)
  pmtiles extract "https://build.protomaps.com/$BUILD.pmtiles" "$OUT/$id.pmtiles" --bbox="$bbox" --maxzoom="$MAXZOOM"
done

# --- 3. Style layers (Hebrew labels) and offline fonts and sprites.
node scripts/layers.mjs light > "$OUT/layers.json"
node scripts/layers.mjs dark > "$OUT/layers-dark.json"
rm -rf "$WORK/basemaps-assets"
git clone --depth 1 https://github.com/protomaps/basemaps-assets "$WORK/basemaps-assets"
# only the fonts the style uses (all Unicode ranges, Hebrew included) and the light and dark sprites
FONTS=$(jq -rs '[.. | objects | ."text-font"? // empty | .. | strings | select(startswith("Noto Sans"))] | unique | .[]' "$OUT/layers.json" "$OUT/layers-dark.json")
( cd "$WORK/basemaps-assets"
  args=()
  # a font the assets do not have (scripts we do not need, e.g. Devanagari) is skipped
  while IFS= read -r f; do if [ -d "fonts/$f" ]; then args+=("fonts/$f"); else echo "font not in assets, skipped: $f" >&2; fi; done <<< "$FONTS"
  ls fonts/"Noto Sans Regular"/1280-1535.pbf > /dev/null   # Hebrew glyphs
  zip -qr "../../$OUT/assets.zip" "${args[@]}" sprites/v4/light* sprites/v4/dark* )

# --- 4. Manifest.
python3 scripts/manifest.py "$OUT" "$BUILD" "${OSM_DATE:-}" > "$OUT/manifest.json"
cat "$OUT/manifest.json"
ls -la "$OUT"

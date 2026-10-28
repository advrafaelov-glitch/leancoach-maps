# leancoach-maps

קבצי המפה של אפליקציית LeanCoach, לפי אזור. אין כאן קוד של האפליקציה – רק נתוני מפה ציבוריים.

| קובץ (לכל אזור) | מה יש בו | מקור |
| --- | --- | --- |
| `<id>.osm.pbf` | כבישים ומקומות עם שם – חיפוש, ניווט ועיקולים במנוע | OpenStreetMap דרך Geofabrik |
| `<id>.pmtiles` | תמונת המפה, שמורה בטלפון | Protomaps basemap (OpenStreetMap) |

ובנוסף: `layers.json` ו-`layers-dark.json` (עיצוב המפה בהיר וכהה, שמות בעברית), `assets.zip` (גופנים וסמלים), `manifest.json` (רשימת האזורים, גדלים ו-sha256).

האזורים מוגדרים ב-`regions.json`. הבנייה: `.github/workflows/build-maps.yml`, פעם בחודש ובהפעלה ידנית (Actions → build-maps → Run workflow). כל בנייה מתפרסמת כ-Release; האפליקציה מורידה מ-`releases/latest/download/manifest.json`.

## כבישי בדיקה

`test-roads.json`: כבישים בארץ ובעולם לסימון סוף עיקולים (ספסל הבדיקה באפליקציה). לכל כביש: הקטעים שלו מ‑OpenStreetMap כ‑`<id>.kml` ותמונת מפה קטנה `<id>.pmtiles`. הבנייה: `.github/workflows/build-test-roads.yml` (בכל שינוי ברשימה, או ידנית), ל‑Release בשם `test-roads` – לא latest, כדי לא לגעת במפות של ישראל.

## רישיון

הנתונים © OpenStreetMap contributors, ברישיון [ODbL](https://opendatacommons.org/licenses/odbl/). תמונת המפה: [Protomaps](https://protomaps.com) basemap, יצירה נגזרת של OpenStreetMap ב-ODbL. יש לציין "© OpenStreetMap contributors" בכל מקום שהמפה מוצגת.

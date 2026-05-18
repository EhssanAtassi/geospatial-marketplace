# Example: DWG → MongoDB

End-to-end example showing how a CAD drawing (DWG) gets converted to MongoDB documents. This is the trickiest format combination — DWG has no CRS, layers carry semantic meaning, and MongoDB requires EPSG:4326 GeoJSON.

## Input

```
/data/site-plans/project-alpha.dwg     # 4.8 MB AutoCAD 2018 drawing
```

**Inspection summary** (from `/gis-to-db:inspect`):

- Format: DWG (via LibreDWG → DXF pipeline)
- 6 layers found:
  - `PARCELS` — 47 LWPOLYLINE entities (closed → Polygon)
  - `BUILDINGS` — 31 LWPOLYLINE entities (closed → Polygon)
  - `ROADS` — 12 LWPOLYLINE (open → LineString), 6 LINE
  - `DEFPOINTS` — 284 POINT (AutoCAD-internal; skip)
  - `DIMENSION` — 142 DIMENSION (annotation; skip)
  - `TITLE` — 23 LWPOLYLINE (title block; skip)
- **CRS: MISSING** — drawing was produced in survey-local meters; user must supply source CRS.

**User-supplied context** (gathered by validator agent before conversion):

- Source CRS: `EPSG:32637` (UTM Zone 37N — drawing is in meters east/north of a survey origin near Damascus).
- Layers to ingest: `PARCELS` only (the headline data).
- Entity types: `LWPOLYLINE` (closed) → Polygon.

## Command

```bash
python gis_convert.py /data/site-plans/project-alpha.dwg \
  --target mongo \
  --table-name project_alpha_parcels \
  --source-crs EPSG:32637 \
  --layer PARCELS \
  --ddl \
  --limit 3
```

## Output (chat-truncated)

```javascript
-- Source: /data/site-plans/project-alpha.dwg
-- Format: DWG
-- Target: mongo (SRID 4326)
-- Full output saved to: /tmp/project_alpha_parcels.js
-- Features emitted: 47 (chat truncated to 3)

// MongoDB index for project_alpha_parcels
db.project_alpha_parcels.createIndex({ "geometry": "2dsphere" });

db.project_alpha_parcels.insertMany([
  {"layer": "PARCELS", "dxftype": "LWPOLYLINE", "geometry": {"type": "Polygon", "coordinates": [[[36.30134, 33.51247], [36.30178, 33.51247], [36.30178, 33.51289], [36.30134, 33.51289], [36.30134, 33.51247]]]}}
 ,{"layer": "PARCELS", "dxftype": "LWPOLYLINE", "geometry": {"type": "Polygon", "coordinates": [[[36.30178, 33.51247], [36.30224, 33.51247], [36.30224, 33.51289], [36.30178, 33.51289], [36.30178, 33.51247]]]}}
 ,{"layer": "PARCELS", "dxftype": "LWPOLYLINE", "geometry": {"type": "Polygon", "coordinates": [[[36.30224, 33.51247], [36.30248, 33.51247], [36.30248, 33.51268], [36.30224, 33.51268], [36.30224, 33.51247]]]}}
// ⚠ Output truncated to 3 features for chat readability. Full output saved to /tmp/project_alpha_parcels.js.
]);

// Run with: mongosh <connection-string> /tmp/project_alpha_parcels.js
```

## What happened under the hood

1. **LibreDWG conversion**: `dwg2dxf -o /tmp/<random>.dxf project-alpha.dwg` produced a temporary DXF file. Took ~1.5s for a 4.8MB drawing.
2. **ezdxf parsing**: opened the DXF, iterated entities in model space, filtered to layer `PARCELS`.
3. **Entity-to-geometry mapping**: each LWPOLYLINE was converted to a Shapely `Polygon` via the canonical mapper (`_dxf_entity_to_geom`).
4. **Reprojection**: `pyproj.Transformer.from_crs("EPSG:32637", "EPSG:4326", always_xy=True)` transformed each polygon's coordinates from UTM Zone 37N meters → WGS84 lat/lng degrees.
5. **MongoDB document construction**: each feature became `{"layer": "PARCELS", "dxftype": "LWPOLYLINE", "geometry": <GeoJSON>}` — properties spread at root, geometry under the `geometry` key.
6. **Output format**: `insertMany()` with one document per line, leading commas for clean diffs.
7. **Index**: 2dsphere index created via `createIndex` — must be on `geometry` field name.

## Running the output

```bash
# Local MongoDB
mongosh "mongodb://localhost:27017/realestate" /tmp/project_alpha_parcels.js

# Verify
mongosh "mongodb://localhost:27017/realestate" \
  --eval "db.project_alpha_parcels.countDocuments({})"
# 47
```

### Sanity-check that the index works

```javascript
// Find parcels within 100m of the survey reference point
db.project_alpha_parcels.find({
  geometry: {
    $near: {
      $geometry: { type: "Point", coordinates: [36.30, 33.51] },
      $maxDistance: 100
    }
  }
}).limit(5);
```

If this returns features, the 2dsphere index is healthy and the coordinates are in WGS84 (lng, lat).

If this returns nothing OR returns features clearly in the wrong place:

- Check coordinate order — `[lng, lat]` not `[lat, lng]`.
- Verify reprojection succeeded — print one document and check the `coordinates` are degree-scaled values like `[36.30, 33.51]`, not meter-scaled like `[262145, 3712847]`.
- Verify the source CRS was correct.

## Why this workflow matters

DWG → MongoDB is the headline real-estate ingestion path:

- Architects/surveyors deliver site plans as DWG.
- The customer-facing real-estate app uses MongoDB for fast read patterns and Leaflet/Mapbox for rendering.
- Without this plugin, the path from DWG to MongoDB documents involves:
  1. Open DWG in AutoCAD or QGIS (commercial / heavy).
  2. Manually georeference layers (assign CRS, sometimes pick control points).
  3. Filter to relevant layers.
  4. Export to Shapefile or GeoJSON.
  5. Reproject to 4326.
  6. Write a custom script to convert features to BSON insert documents.
  7. Wire up indexes.

The plugin collapses that to one command.

## Common errors

### "LibreDWG (dwg2dxf) not installed"

Install on Ubuntu/Debian:

```bash
sudo apt-get install libredwg-tools
```

On macOS via Homebrew:

```bash
brew install libredwg
```

Or run inside Docker (the plugin's recommendation):

```bash
docker run --rm -v "$PWD":/work -w /work \
  osgeo/gdal:ubuntu-small-3.8.0 \
  bash -c "apt-get update && apt-get install -y libredwg-tools && \
           pip install ezdxf shapely pyproj fiona && \
           python /scripts/gis_convert.py site-plan.dwg --target mongo --table-name parcels --source-crs EPSG:32637"
```

### "LibreDWG conversion failed"

LibreDWG handles most AutoCAD versions through 2018. Files saved in AutoCAD 2024+ may fail. Workaround:

1. Open the DWG in any AutoCAD-compatible tool.
2. Save As → AutoCAD 2018 DWG format.
3. Re-run the conversion.

Or use ODA File Converter:

```bash
ODAFileConverter <in_dir> <out_dir> "ACAD2018" "DXF" "0" "1"
```

Then run `gis_convert.py` on the resulting DXF directly.

### Polygons appear inverted or self-intersecting

DWG drawings sometimes have polygons with reversed vertex order (clockwise instead of counter-clockwise). MongoDB's 2dsphere index validates polygon ring orientation per the right-hand rule. If MongoDB rejects insertions with `Loop is not valid` or `more than one direction`, fix the orientation:

In `gis_convert.py` (post-v0.1 enhancement), wrap polygon construction with:

```python
from shapely.geometry import polygon as _polygon
fixed = _polygon.orient(geom, sign=1.0)
```

This forces counter-clockwise (CCW) for outer rings, which MongoDB expects.

### "duplicate key error" on re-runs

The generated documents have no `_id` field, so MongoDB auto-generates ObjectIds. Each run creates new documents — running the same file twice doubles the data. To make ingestion idempotent, manually add a stable identifier (e.g. `parcel_id` from the source attributes) and create a unique index before insertion.

## Tip: scripting around the truncation

When you want to ingest the full output programmatically without copy-pasting from chat:

```bash
# Generate
python gis_convert.py site.dwg --target mongo --table-name parcels --source-crs EPSG:32637 --layer PARCELS --ddl --limit 0  # --limit 0 disables truncation (v0.2)

# Or simply ingest the /tmp/ file directly (already untruncated)
mongosh "mongodb://localhost:27017/realestate" /tmp/parcels.js
```

The `/tmp/<table>.js` file always contains the complete output regardless of `--limit`.

# DWG/DXF Inspection Pipeline

DWG and DXF are CAD formats, not GIS formats. They lack CRS metadata, organize data by layer (which carries semantic meaning by convention), and may include non-geographic entities (text, dimensions, blocks). Inspection treats them differently from Shapefile / `.gdb` / GeoJSON.

## Pipeline overview

```
.dwg ─[LibreDWG dwg2dxf]─► /tmp/<name>.dxf ─[ezdxf]─► layer inventory + entity counts
.dxf ──────────────────────────────────────[ezdxf]─► layer inventory + entity counts
```

For DWG inputs the script:

1. Verifies `dwg2dxf` is on PATH. If missing, emits a warning recommending Docker (`osgeo/gdal:ubuntu-small-3.8.0 + libredwg-tools`) and returns an empty report.
2. Creates a temporary DXF in `/tmp/`.
3. Calls `dwg2dxf -o /tmp/<name>.dxf <input.dwg>`.
4. Inspects the resulting DXF using ezdxf.
5. Deletes the temp DXF.

## What the inspector reports

For each DWG **layer** (not "feature class" — DWG layers are presentation buckets):

- **Layer name** (verbatim from the drawing).
- **Total entity count** across all entity types in that layer.
- **Per-entity-type counts** — how many `LWPOLYLINE`s, `LINE`s, `CIRCLE`s, etc.
- **Dominant geometry type** mapped to a Shapely-style name.
- **Sample entities** of the dominant type (handle + 200-char preview).
- **Standing warning**: "DXF/DWG has no CRS metadata. User must supply source CRS before ingestion."

There are NO bounds reported for DXF/DWG layers — coordinate ranges in DWG/DXF are typically in millimeters of a survey-local origin, and reporting them without CRS context would be misleading.

## Entity type → geometry mapping (inspection-time)

The script maps each entity type to a "geometry type" string for display purposes only — actual geometry extraction happens during `/gis-to-db:convert` (using the same mapping):

| DXF entity | Reported geometry type |
|---|---|
| `POINT` | `Point` |
| `LINE` | `LineString` |
| `LWPOLYLINE` (closed) | `Polygon` |
| `LWPOLYLINE` (open) | `LineString` |
| `POLYLINE` (legacy 3D) | `Polygon` or `LineString` |
| `CIRCLE` | `Polygon (approximated)` |
| `ARC` | `LineString (sampled)` |
| `ELLIPSE` | `Polygon` or `LineString` |
| `SPLINE` | `LineString (sampled)` |
| `HATCH` | `Polygon (boundary)` |
| `TEXT` / `MTEXT` | `(annotation — skipped)` |
| `DIMENSION` | `(annotation — skipped)` |
| `INSERT` | `(block reference — skipped unless expanded)` |

If a layer has a mix of types, the **most common type's mapping** is reported as the layer's geometry type. The full per-type breakdown is preserved in the `fields` array of the `LayerReport`.

## Layer-name conventions

Real-world DWG drawings follow loose conventions. Use these hints when interpreting inspection output:

### Real estate / land development

| Layer name pattern | Likely content |
|---|---|
| `PARCEL`, `PARCELS`, `LOT`, `LOTS`, `PROPERTY` | Land parcel boundaries (Polygon) |
| `BUILDING`, `BUILDINGS`, `FOOTPRINT`, `STRUCTURE` | Building footprints (Polygon) |
| `ROAD`, `STREET`, `CENTERLINE`, `CL_*` | Road centerlines (LineString) |
| `EDGE_PAVEMENT`, `CURB`, `EOP` | Pavement edges (LineString or Polygon) |
| `SIDEWALK`, `WALK` | Walkways (Polygon or LineString) |

### Infrastructure / utilities

| Layer name pattern | Likely content |
|---|---|
| `WATER_*`, `WTR`, `WATERMAIN` | Water utilities (LineString) |
| `SEWER`, `SAN_*`, `STORM_*` | Sewer lines (LineString) |
| `GAS_*`, `OIL_*` | Gas/oil pipelines (LineString) |
| `ELEC_*`, `POWER`, `OVERHEAD`, `UNDERGROUND` | Electrical lines (LineString) |
| `TELECOM`, `FIBER`, `COMM` | Telecommunications (LineString) |
| `MH`, `MANHOLE`, `CB`, `CATCHBASIN` | Point features (Point) |

### Drafting / non-geographic (skip)

| Layer name pattern | Why skip |
|---|---|
| `0` (default layer) | Mixed/unintentional content |
| `DEFPOINTS` | AutoCAD-internal; non-printing helper points |
| `DIMENSION*`, `DIM*` | Dimension annotations |
| `TEXT*`, `ANNO*`, `LABEL*` | Text annotations |
| `BORDER`, `TITLE`, `SHEET`, `NORTHARROW`, `LEGEND` | Paper-space drafting elements |
| `VIEWPORT` | Paper-space viewport boundaries |
| `HATCH*`, `FILL*` | Cosmetic fills (sometimes useful — judge per drawing) |
| `XREF`, `*_REF` | External reference layers (data is in another file) |

The inspector reports all layers regardless of name — it's the user's job to choose which ones to ingest during `/gis-to-db:convert` or `/gis-to-db:add-module`.

## Drawing units

DXF stores units via the `$INSUNITS` header variable. The inspector does NOT currently report this — it's something to add in v0.2. Common values:

| `$INSUNITS` value | Unit |
|---|---|
| 0 | Unspecified |
| 1 | Inches |
| 2 | Feet |
| 4 | Millimeters |
| 5 | Centimeters |
| 6 | Meters |
| 8 | Microinches |
| 9 | Mils |

When the user reports "the coordinates look weird" — too large or too small — check `$INSUNITS`. A drawing in millimeters of a survey origin will have coordinates like `(123456789, 234567890)`. These are NOT lat/lng degrees; they're millimeters east/north of `(0, 0)` and need both **unit conversion** (mm→m) and **CRS interpretation** (offset → lat/lng via survey control point) before they can be treated as geographic data.

## When inspection isn't enough

The inspector reports the **structure** of a DWG/DXF but not the **meaning**. Some questions can only be answered by a domain expert or the drawing's author:

- "What CRS were the drawings produced in?" — Inspector cannot guess; user must answer.
- "Which layers contain the parcels I care about?" — Inspector lists all layers; user chooses.
- "Which entity types should I ingest from this layer?" — Inspector counts each type; user picks.
- "Are these millimeters of a local origin, or meters of UTM, or degrees?" — Inspector cannot tell from numbers alone if the drawing has plausible-looking values in multiple unit systems.

The inspect skill's job is to surface every uncertainty as a warning so the user can answer them before invoking `/gis-to-db:convert` or downstream skills.

## LibreDWG fallback chain

If `dwg2dxf` fails, the script reports the failure and recommends alternatives:

1. **ODA File Converter** — free for personal use, more robust than LibreDWG for AutoCAD 2018+. Headless mode:
   ```bash
   ODAFileConverter <in_dir> <out_dir> "ACAD2018" "DXF" "0" "1"
   ```
2. **Manual export from AutoCAD** — open the DWG in AutoCAD, run `SAVEAS` → DXF.
3. **Online conversion** — last resort, raises privacy concerns for proprietary drawings. Do NOT recommend.

The script does not implement ODA fallback in v0.1 — adding it is a v0.2 task.

## Inspection performance

- Shapefile / GeoJSON < 100MB: under 1s for full report including 3 sample features.
- `.gdb` with 5–10 feature classes, 100k features total: 2–5s.
- DXF < 10MB (typical site plan): 1–2s for ezdxf to parse + iterate.
- DWG of equivalent size: add 3–10s for `dwg2dxf` conversion.

For very large files (>500MB Shapefile or >1M features in `.gdb`), the script may take 30s+ because fiona's `len(src)` iterates over the file. v0.2 could cache the count or accept a `--no-count` flag.

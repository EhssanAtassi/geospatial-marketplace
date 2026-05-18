# Inspect Output Format

The `gis_inspect.py` script emits a deterministic JSON structure when invoked with `--json`. Without the flag, it prints a markdown report rendered from the same data. This document defines the schema and the markdown rendering rules.

## JSON Schema

Top-level object:

```json
{
  "path": "/abs/path/to/file.shp",
  "size_bytes": 1247589,
  "format": "Shapefile",
  "driver": "ESRI Shapefile",
  "layers": [<LayerReport>, ...],
  "environment": {
    "fiona": "1.9.5",
    "gdal": "3.8.0",
    "ezdxf": "1.2.0",
    "libredwg": true,
    "fiona_drivers": ["ESRI Shapefile", "GeoJSON", "..."]
  },
  "warnings": ["..."],
  "next_steps": ["..."]
}
```

### `LayerReport` object

```json
{
  "name": "Parcels",
  "geometry_type": "Polygon",
  "feature_count": 1247,
  "crs_epsg": 32637,
  "crs_wkt": "PROJCS[...]",
  "bounds": [37.0, 34.5, 37.5, 35.0],
  "fields": [
    {"name": "parcel_id", "type": "str:64"},
    {"name": "area_sqm", "type": "float"}
  ],
  "sample_features": [<SampleFeature>, ...],
  "warnings": ["..."]
}
```

For fiona-backed formats (Shapefile, .gdb, GeoJSON, KML, GeoPackage):

- `name` is the layer / feature class name. `None` for single-layer formats like Shapefile and GeoJSON.
- `geometry_type` comes from fiona's schema — one of `"Point"`, `"LineString"`, `"Polygon"`, `"MultiPoint"`, `"MultiLineString"`, `"MultiPolygon"`, `"GeometryCollection"`, or `"3D <Type>"` for Z-bearing variants.
- `crs_epsg` is the EPSG code if extractable from the CRS, otherwise `null`.
- `crs_wkt` is the WKT string from `.prj` or equivalent, otherwise `null`.
- `bounds` is `[minx, miny, maxx, maxy]` in the source CRS units.
- `fields` lists attribute columns; type strings follow fiona's format (`"str:N"`, `"int"`, `"float"`, `"date"`).

For DXF / DWG inputs:

- One `LayerReport` per **DWG layer** (not per fiona layer — different concept).
- `geometry_type` is the dominant entity type mapped to a Shapely-style name (e.g. `"Polygon (approximated)"` for CIRCLEs, `"LineString (sampled)"` for ARCs).
- `crs_epsg` and `crs_wkt` are always `null` — DXF/DWG lack CRS metadata.
- `fields` contains one entry per DXF entity type present in the layer, with `type` as `"count=N"`.

### `SampleFeature` object

For fiona-backed formats:

```json
{
  "id": "42",
  "geometry_preview": "POLYGON ((37.1 34.8, 37.2 34.8, ...))",
  "properties": {"parcel_id": "P-001", "area_sqm": 1247.5}
}
```

`geometry_preview` is the feature's WKT truncated to 200 chars (with an ellipsis if truncated). The full geometry is not included to keep reports readable; use `/gis-to-db:convert` for full output.

For DXF / DWG:

```json
{
  "dxftype": "LWPOLYLINE",
  "handle": "1A2B",
  "preview": "LWPOLYLINE(#1A2B)..."
}
```

## Markdown Rendering Rules

When invoked without `--json`, the script renders the JSON into the following markdown layout:

```markdown
# Inspection Report — `<path>`

## File
- **Format**: <format>
- **Driver**: <driver>
- **Size**: <bytes>

## Environment
- GDAL: `<version or MISSING>`
- fiona: `<version or MISSING>`
- ezdxf: `<version or MISSING>`
- LibreDWG: `<present or MISSING>`

## Layer 1: `<name>`
- Geometry: **<geometry_type>**
- Features: **<count>**
- CRS: **EPSG:<n>** or **MISSING — user must supply source CRS**
- Bounds: (minx, miny) → (maxx, maxy)

### Attributes
| Name | Type |
|---|---|
| `<field>` | <type> |

### Sample features
**Feature 1:**
```json
{ ... }
```

### Warnings
- ⚠ <warning>

## Next steps
- <suggested next command>
```

### Rendering details

- **Field types** are shown as-is from fiona (`str:64`, `int`, `float`). For DXF, the `type` column shows `count=N` to indicate how many entities of that type exist.
- **CRS rendering** prefers EPSG code; falls back to "custom WKT — see JSON output" if only WKT is available; shows "**MISSING**" with the warning if neither.
- **Bounds** are rendered with 6 decimal places (sufficient precision for ~10cm at WGS84 equator).
- **Sample features** are emitted as fenced JSON blocks with `json.dumps(..., indent=2, default=str)`. Dates and other non-JSON-native values are coerced via `default=str`.
- **Warnings** use a ⚠ prefix (single character, unicode safe) for visual distinction.
- **Next steps** are always at the bottom and always present (even if just "Source CRS is missing").

## Warning Catalog

The script emits these warnings under specific conditions. The calling skill should surface them prominently:

| Warning text (substring) | Condition | Severity |
|---|---|---|
| "No CRS detected" | fiona `src.crs` is empty/None | High — blocks ingestion |
| "no CRS metadata" | DXF/DWG input | High — blocks ingestion |
| "Source CRS is EPSG:N; reprojection to EPSG:4326 will be required" | Source CRS is set but ≠ 4326 | Medium — automatic during ingestion |
| "Layer '<name>' not found" | `--layer` filter targeted a nonexistent layer | High — invalid input |
| "Failed to read layer" | fiona open() raised | High — investigate |
| "ezdxf not installed" | DXF input but no ezdxf | High — install or use Docker |
| "LibreDWG (`dwg2dxf`) not installed" | DWG input but no `dwg2dxf` | High — install or use Docker |
| "LibreDWG conversion failed" | `dwg2dxf` exited non-zero | High — try ODA File Converter |
| "No entities found in model space" | DXF/DWG with empty model space | Medium — file may have paper-space only |

## Next-Step Heuristics

The script's `build_next_steps()` produces a list of recommended commands:

1. If any layer has a CRS-missing warning, suggest re-inspecting after the user supplies the source CRS via `--source-crs EPSG:N`.
2. If features were found, suggest:
   - `/gis-to-db:convert <path> --target <db> --limit 10` for a quick preview.
   - `/gis-to-db:scaffold-service --db-target <target>` for a full service.
   - `/gis-to-db:add-module --host-dir <path>` to wire into an existing app.

The skill rendering the report should NOT add additional next-step suggestions beyond what the script emits — keeping them consistent across invocations.

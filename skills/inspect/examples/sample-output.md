# Sample Inspection Reports

Real examples of `gis_inspect.py` output for the formats this plugin handles. Use these to verify rendering correctness and as reference for what users will see.

## Example 1: Shapefile (cadastral parcels)

**Command:**
```
$ python gis_inspect.py /data/syria-parcels/damascus.shp
```

**Output:**
```markdown
# Inspection Report — `/data/syria-parcels/damascus.shp`

## File
- **Format**: Shapefile
- **Driver**: ESRI Shapefile
- **Size**: 18,247,389 bytes

## Environment
- GDAL: `3.8.0`
- fiona: `1.9.5`
- ezdxf: `1.2.0`
- LibreDWG: `present`

## Layer 1: `(default)`
- Geometry: **Polygon**
- Features: **12,847**
- CRS: **EPSG:32637**
- Bounds: (252413.789012, 3704512.345678) → (276891.234567, 3722098.876543)

### Attributes
| Name | Type |
|---|---|
| `parcel_id` | str:32 |
| `area_sqm` | float |
| `zone` | str:32 |
| `owner` | str:128 |
| `tax_value` | int |
| `last_survey` | date |

### Sample features
**Feature 1:**
```json
{
  "id": "0",
  "geometry_preview": "POLYGON ((262145.32 3712847.65, 262189.45 3712847.65, 262189.45 3712891.78, 262145.32 3712891.78, 262145.32 3712847.65))",
  "properties": {
    "parcel_id": "DM-001-247",
    "area_sqm": 1947.5,
    "zone": "residential",
    "owner": "Ministry of Awqaf",
    "tax_value": 0,
    "last_survey": "2019-03-14"
  }
}
```

### Warnings
- ⚠ Source CRS is EPSG:32637; reprojection to EPSG:4326 will be required for MongoDB and most web targets.

## Next steps
- To preview SQL/MongoDB output: `/gis-to-db:convert /data/syria-parcels/damascus.shp --target <postgis|mongo|mysql> --limit 10`.
- To scaffold a full ingestion service: `/gis-to-db:scaffold-service --db-target <target>`.
- To wire ingestion into an existing app: `/gis-to-db:add-module --host-dir <path>`.
```

## Example 2: ESRI File Geodatabase (multi-layer cadastral)

**Command:**
```
$ python gis_inspect.py /data/cadastre.gdb --features-sample 2
```

**Output (excerpt):**
```markdown
# Inspection Report — `/data/cadastre.gdb`

## File
- **Format**: ESRI File Geodatabase
- **Driver**: OpenFileGDB
- **Size**: 247,389,012 bytes

## Layer 1: `Parcels`
- Geometry: **MultiPolygon**
- Features: **84,392**
- CRS: **EPSG:32637**
- Bounds: (245000.000, 3690000.000) → (290000.000, 3735000.000)

### Attributes
| Name | Type |
|---|---|
| `OBJECTID` | int |
| `PARCEL_ID` | str:64 |
| `AREA_SQM` | float |
| `ZONE_CODE` | str:8 |
| `OWNER_NAME` | str:200 |

...

## Layer 2: `Buildings`
- Geometry: **MultiPolygon**
- Features: **127,841**
- CRS: **EPSG:32637**
- Bounds: (245100.000, 3690200.000) → (289900.000, 3734800.000)

...

## Layer 3: `Roads`
- Geometry: **LineString**
- Features: **8,213**
- CRS: **EPSG:32637**
...

### Warnings
- ⚠ Source CRS is EPSG:32637; reprojection to EPSG:4326 will be required for MongoDB and most web targets.

## Next steps
- ...
```

## Example 3: DWG site plan (no CRS, many layers)

**Command:**
```
$ python gis_inspect.py /data/site-plans/project-alpha.dwg
```

**Output:**
```markdown
# Inspection Report — `/data/site-plans/project-alpha.dwg`

## File
- **Format**: DWG
- **Driver**: __libredwg__
- **Size**: 4,872,193 bytes

## Layer 1: `PARCELS`
- Geometry: **Polygon**
- Features: **47**
- CRS: **MISSING** — user must supply source CRS

### Attributes
| Name | Type |
|---|---|
| `LWPOLYLINE` | count=47 |

### Sample features
**Feature 1:**
```json
{
  "dxftype": "LWPOLYLINE",
  "handle": "2A1",
  "preview": "LWPOLYLINE(#2A1)"
}
```

### Warnings
- ⚠ DXF/DWG has no CRS metadata. User must supply source CRS before ingestion.

## Layer 2: `BUILDINGS`
- Geometry: **Polygon**
- Features: **31**
- CRS: **MISSING** — user must supply source CRS
...

## Layer 3: `ROADS`
- Geometry: **LineString**
- Features: **18**
- CRS: **MISSING** — user must supply source CRS

### Attributes
| Name | Type |
|---|---|
| `LWPOLYLINE` | count=12 |
| `LINE` | count=6 |
...

## Layer 4: `DEFPOINTS`
- Geometry: **Point**
- Features: **284**
...
(NOTE: typically skip — AutoCAD-internal helper layer)

## Layer 5: `DIMENSION`
- Geometry: **(annotation — skipped)**
- Features: **142**
...

## Layer 6: `TITLE`
- Geometry: **LineString**
- Features: **23**
...
(NOTE: typically skip — title block, not geographic data)

## Next steps
- Source CRS is missing. Re-run `/gis-to-db:inspect` after the user supplies the source CRS via `--source-crs EPSG:N`.
- To preview SQL/MongoDB output: `/gis-to-db:convert /data/site-plans/project-alpha.dwg --target <postgis|mongo|mysql> --limit 10`.
- To scaffold a full ingestion service: `/gis-to-db:scaffold-service --db-target <target>`.
- To wire ingestion into an existing app: `/gis-to-db:add-module --host-dir <path>`.
```

## Example 4: GeoJSON (well-formed)

**Command:**
```
$ python gis_inspect.py /data/zones.geojson
```

**Output:**
```markdown
# Inspection Report — `/data/zones.geojson`

## File
- **Format**: GeoJSON
- **Driver**: GeoJSON
- **Size**: 247,891 bytes

## Layer 1: `(default)`
- Geometry: **MultiPolygon**
- Features: **142**
- CRS: **EPSG:4326**
- Bounds: (36.123456, 33.456789) → (36.987654, 34.012345)

### Attributes
| Name | Type |
|---|---|
| `zone_id` | str:16 |
| `zone_name` | str:64 |
| `zone_type` | str:32 |
| `description` | str:200 |

### Sample features
**Feature 1:**
```json
{
  "id": "1",
  "geometry_preview": "MULTIPOLYGON (((36.234 33.567, 36.245 33.567, 36.245 33.578, ...)))",
  "properties": {
    "zone_id": "Z-A1",
    "zone_name": "Old City Heritage Zone",
    "zone_type": "heritage",
    "description": "Protected historic district"
  }
}
```

## Next steps
- To preview SQL/MongoDB output: `/gis-to-db:convert /data/zones.geojson --target <postgis|mongo|mysql> --limit 10`.
- To scaffold a full ingestion service: `/gis-to-db:scaffold-service --db-target <target>`.
- To wire ingestion into an existing app: `/gis-to-db:add-module --host-dir <path>`.
```

(No warnings — already in EPSG:4326, no CRS issues, no DWG quirks.)

## Example 5: Missing dependency

**Command:**
```
$ python gis_inspect.py /data/site.dwg
```

**Output when LibreDWG is not installed:**
```markdown
# Inspection Report — `/data/site.dwg`

## File
- **Format**: DWG
- **Driver**: __libredwg__
- **Size**: 4,872,193 bytes

## Environment
- GDAL: `3.8.0`
- fiona: `1.9.5`
- ezdxf: `1.2.0`
- LibreDWG: `MISSING`

## Layer 1: `(default)`
- Geometry: **unknown**
- Features: **0**

### Warnings
- ⚠ LibreDWG (`dwg2dxf`) not installed. Install with: apt-get install libredwg-tools — OR run inspection inside Docker (osgeo/gdal:ubuntu-small + libredwg-tools).

## Next steps
- (none — file could not be parsed)
```

## How the calling skill renders these

The `inspect` SKILL.md invokes `gis_inspect.py` via Bash and pipes the markdown output directly to the user. The skill does NOT add extra prose around the report — the script's output is the authoritative response. The skill's only post-processing is:

1. If the script exits with code 1 (user error) or 2 (parse failure), surface the JSON error from stderr in plain English.
2. If the script exits with code 3 (missing tooling), show the install instructions from the relevant warning AND offer to retry inside Docker.
3. Otherwise, pass through the markdown unchanged.

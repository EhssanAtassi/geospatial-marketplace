# GDAL Toolbox Reference

GDAL/OGR is the universal Swiss Army knife of geospatial I/O. This reference covers what the plugin needs: the Docker image, the Python bindings (fiona, geopandas), DWG/DXF tools (ezdxf, LibreDWG), and `ogr2ogr` for bulk operations.

## The plugin's Docker image of choice

```
osgeo/gdal:ubuntu-small-3.8.0
```

About 600MB. Contains:

- GDAL 3.8.0 + PROJ 9.x
- Python 3.10 + fiona + geopandas
- `ogr2ogr`, `gdalinfo`, `gdaltransform` CLIs

What it does **not** contain by default:

- LibreDWG (`dwg2dxf`) — installed on top
- `ezdxf` Python lib — installed via pip

### Plugin's Dockerfile snippet

```dockerfile
FROM osgeo/gdal:ubuntu-small-3.8.0

# DWG support via LibreDWG
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libredwg-tools && \
    rm -rf /var/lib/apt/lists/*

# Python packages
RUN pip install --no-cache-dir \
    fiona==1.9.* \
    geopandas==0.14.* \
    shapely==2.0.* \
    pyproj==3.6.* \
    ezdxf==1.2.* \
    rich==13.* \
    typer==0.12.*
```

### Running the image ad-hoc

```bash
# Mount current dir, run a one-off inspection
docker run --rm -v "$PWD":/work -w /work \
  osgeo/gdal:ubuntu-small-3.8.0 \
  ogrinfo -al -so parcels.shp

# Interactive shell
docker run --rm -it -v "$PWD":/work -w /work \
  osgeo/gdal:ubuntu-small-3.8.0 \
  bash
```

## fiona — the GIS I/O workhorse

fiona wraps GDAL/OGR with a clean Python API. Used by geopandas internally.

### Reading

```python
import fiona

# List layers (for multi-layer formats: .gdb, .gpkg, KML)
layers = fiona.listlayers("parcels.gdb")

# Open and iterate
with fiona.open("parcels.gdb", layer="Parcels") as src:
    print(src.driver)            # 'OpenFileGDB'
    print(src.schema)            # {'geometry': 'Polygon', 'properties': {...}}
    print(src.crs)               # CRS dict
    print(src.crs_wkt)           # WKT string
    print(src.bounds)            # (minx, miny, maxx, maxy)
    print(len(src))              # feature count

    for feature in src:
        geom = feature['geometry']       # GeoJSON-shaped dict
        props = feature['properties']    # ordered dict
        fid = feature['id']              # feature ID
```

### Writing

```python
schema = {
    "geometry": "MultiPolygon",
    "properties": {
        "parcel_id": "str",
        "area_sqm": "float",
    },
}

with fiona.open(
    "out.geojson",
    "w",
    driver="GeoJSON",
    crs="EPSG:4326",
    schema=schema,
) as dst:
    dst.write({
        "geometry": {"type": "MultiPolygon", "coordinates": [...]},
        "properties": {"parcel_id": "P-001", "area_sqm": 1247.5},
    })
```

### Drivers (`fiona.supported_drivers`)

| Driver | Read | Write | Format |
|---|---|---|---|
| `ESRI Shapefile` | ✓ | ✓ | Shapefile |
| `OpenFileGDB` | ✓ | partial | ESRI File Geodatabase |
| `GeoJSON` | ✓ | ✓ | GeoJSON |
| `LIBKML` | ✓ | ✓ | KML, KMZ |
| `GPKG` | ✓ | ✓ | GeoPackage |
| `DXF` | ✓ | ✓ | DXF (limited — use ezdxf instead) |
| `CSV` | ✓ | ✓ | CSV with WKT or lat/lng columns |

### Streaming large files

```python
import fiona
with fiona.open(path) as src:
    # Slice without loading all features
    for feature in src.filter(bbox=(37.0, 34.5, 37.5, 35.0)):
        ...
```

`filter(bbox=...)` pushes the filter to GDAL — much faster than reading everything and filtering in Python.

## geopandas — fiona + pandas

For when DataFrame ergonomics matter:

```python
import geopandas as gpd

gdf = gpd.read_file("parcels.shp")
print(gdf.crs)                    # CRS object
print(gdf.geometry.geom_type.unique())
print(gdf.head())

# Reproject all geometries
gdf = gdf.to_crs("EPSG:4326")

# Filter by bounding box
clipped = gdf.clip([37.0, 34.5, 37.5, 35.0])

# Write
gdf.to_file("parcels-4326.geojson", driver="GeoJSON")
```

geopandas is heavier (pulls in numpy + pandas) but unbeatable for analytics workflows. For pure ingestion, fiona is leaner.

## ogr2ogr — the CLI converter

The fastest way to bulk-convert one GIS format to another. Used by the plugin's templates as a fallback when Python in-process isn't viable.

### Format-to-format conversion

```bash
# Shapefile → GeoJSON, reprojected to 4326
ogr2ogr \
  -f GeoJSON \
  -t_srs EPSG:4326 \
  -s_srs EPSG:32637 \
  out.geojson \
  parcels.shp

# Shapefile → PostGIS direct
ogr2ogr \
  -f "PostgreSQL" \
  PG:"host=localhost user=postgres dbname=mydb password=secret" \
  parcels.shp \
  -nln parcels \
  -lco GEOMETRY_NAME=geom \
  -lco PRECISION=NO \
  -t_srs EPSG:4326 \
  -nlt PROMOTE_TO_MULTI

# .gdb → PostGIS (specific layer)
ogr2ogr \
  -f "PostgreSQL" \
  PG:"host=localhost user=postgres dbname=mydb" \
  source.gdb \
  Parcels \
  -nln parcels \
  -t_srs EPSG:4326 \
  -nlt PROMOTE_TO_MULTI

# .gdb → MongoDB (via GeoJSON intermediate)
ogr2ogr -f GeoJSONSeq -t_srs EPSG:4326 /tmp/parcels.geojsonl source.gdb Parcels
mongoimport --db mydb --collection parcels --file /tmp/parcels.geojsonl --type json
```

### Useful flags

| Flag | Meaning |
|---|---|
| `-f <driver>` | Output driver (e.g. `GeoJSON`, `PostgreSQL`, `MySQL`, `MongoDBv3`) |
| `-t_srs EPSG:N` | Target SRID (reproject) |
| `-s_srs EPSG:N` | Override source SRID (when `.prj` is wrong or missing) |
| `-nln <name>` | Output layer/table name |
| `-nlt <type>` | Force output geometry type (`POINT`, `POLYGON`, `MULTIPOLYGON`, `PROMOTE_TO_MULTI`) |
| `-where "<sql>"` | Filter features at read time (e.g. `-where "zone='residential'"`) |
| `-clipsrc xmin ymin xmax ymax` | Clip by bounding box |
| `-progress` | Show progress for large operations |
| `-skipfailures` | Continue on per-feature errors instead of aborting |
| `-overwrite` | Replace existing output (PostGIS / file targets) |
| `-append` | Add to existing output instead of overwriting |
| `-lco <key>=<value>` | Layer creation option (driver-specific) |

### Inspecting without converting

```bash
# Full summary, no feature dump
ogrinfo -al -so parcels.shp

# List layers in a multi-layer source
ogrinfo source.gdb

# One-line schema
ogrinfo -ro -al -geom=NO -fields=YES source.shp | head -40

# Field stats (min/max/distinct values)
ogrinfo -sql "SELECT MIN(area_sqm), MAX(area_sqm), COUNT(DISTINCT zone) FROM parcels" parcels.shp
```

## ezdxf — DXF parser

Pure-Python DXF reader. The DWG → DXF → ezdxf pipeline is how the plugin handles DWG.

```python
import ezdxf

doc = ezdxf.readfile("site-plan.dxf")
msp = doc.modelspace()

# Header info
print(doc.header['$INSUNITS'])    # 1=in, 4=mm, 6=m
print(doc.header.get('$ACADVER')) # 'AC1027' (AutoCAD 2013) etc.

# All layers in the drawing
for layer in doc.layers:
    print(layer.dxf.name, layer.dxf.color)

# Query entities by type and layer
entities = msp.query("LWPOLYLINE[layer=='PARCELS']")
for ent in entities:
    points = [(x, y) for x, y, *_ in ent.get_points()]
    closed = ent.closed
    layer = ent.dxf.layer
```

### Entity → Shapely converter (canonical pattern)

```python
import ezdxf
from shapely.geometry import Point, LineString, Polygon
import math

def entity_to_geometry(entity):
    dxftype = entity.dxftype()

    if dxftype == "POINT":
        x, y, *_ = entity.dxf.location
        return Point(x, y)

    if dxftype == "LINE":
        return LineString([
            (entity.dxf.start[0], entity.dxf.start[1]),
            (entity.dxf.end[0], entity.dxf.end[1]),
        ])

    if dxftype == "LWPOLYLINE":
        points = [(p[0], p[1]) for p in entity.get_points()]
        if entity.closed and len(points) >= 3:
            return Polygon(points)
        return LineString(points)

    if dxftype == "POLYLINE":
        points = [(v.dxf.location[0], v.dxf.location[1]) for v in entity.vertices]
        if entity.is_closed and len(points) >= 3:
            return Polygon(points)
        return LineString(points)

    if dxftype == "CIRCLE":
        cx, cy, *_ = entity.dxf.center
        radius = entity.dxf.radius
        # Approximate as 64-gon
        points = [
            (cx + radius * math.cos(theta), cy + radius * math.sin(theta))
            for theta in (i * 2 * math.pi / 64 for i in range(64))
        ]
        return Polygon(points)

    if dxftype == "ARC":
        cx, cy, *_ = entity.dxf.center
        r = entity.dxf.radius
        start_a = math.radians(entity.dxf.start_angle)
        end_a = math.radians(entity.dxf.end_angle)
        if end_a < start_a:
            end_a += 2 * math.pi
        steps = max(16, int((end_a - start_a) / (math.pi / 32)))
        points = [
            (cx + r * math.cos(start_a + i * (end_a - start_a) / steps),
             cy + r * math.sin(start_a + i * (end_a - start_a) / steps))
            for i in range(steps + 1)
        ]
        return LineString(points)

    return None  # Unsupported entity types: TEXT, MTEXT, DIMENSION, HATCH, INSERT, SPLINE
```

For SPLINE and HATCH, use `ezdxf.math` flattening utilities — out of scope for v0.1.

## LibreDWG — DWG → DXF converter

CLI tool from the LibreDWG project (GPL).

```bash
# Convert DWG to DXF
dwg2dxf -o /tmp/site-plan.dxf site-plan.dwg

# Convert directory of DWGs
for f in *.dwg; do
    dwg2dxf -o "/tmp/$(basename "$f" .dwg).dxf" "$f"
done

# Verify the DXF was produced
test -s /tmp/site-plan.dxf && echo "OK"
```

### Versions supported

LibreDWG ≥ 0.12 handles AutoCAD R12 through 2018 reliably. R2018+ (AC1032 and later) may have edge-case failures.

### Failure mode

`dwg2dxf` exits non-zero on parse failure and emits errors to stderr. Always check return code:

```bash
if ! dwg2dxf -o /tmp/out.dxf input.dwg; then
    echo "LibreDWG failed — try ODA File Converter as fallback" >&2
    exit 1
fi
```

### ODA File Converter (fallback)

Free for personal use, restricted commercial. Headless invocation:

```bash
ODAFileConverter <in_dir> <out_dir> "ACAD2018" "DXF" "0" "1"
```

Parameters: output version (`ACAD2018` = R2018), output format (`DXF` or `DWG`), recurse subdirs (`0|1`), audit (`0|1`).

## Common-task one-liners

```bash
# Get the CRS of a shapefile
ogrinfo -ro -al -so parcels.shp | grep -i "spatial reference"

# Convert .gdb to GeoPackage (single file, queryable)
ogr2ogr -f GPKG parcels.gpkg source.gdb

# Get bounding box of a layer
ogrinfo -ro -al -so parcels.shp | grep "^Extent"

# Convert long-form GeoJSON to GeoJSON Text Sequences (newline-delimited)
ogr2ogr -f GeoJSONSeq parcels.geojsonl parcels.geojson

# Reproject every shapefile in a directory in-place
for f in *.shp; do
    ogr2ogr -t_srs EPSG:4326 "/tmp/$(basename "$f")" "$f"
    mv "/tmp/$(basename "$f")" "$f"
done
```

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `ERROR 4: Failed to read projection info` | Missing or malformed `.prj` | Pass `-s_srs EPSG:N` explicitly |
| `ERROR 1: PROJ: proj_create_from_database: ...` | PROJ grid files missing in container | Install `proj-data` package |
| `Cannot find driver "FileGDB"` | Wrong driver name | Use `OpenFileGDB` (open-source) instead |
| `LIBKML driver not available` | KML support not compiled in | Use `osgeo/gdal:ubuntu-small` (default build has LIBKML) |
| ezdxf `DXFStructureError` | Malformed DXF | Try LibreDWG re-round-trip: DWG→DXF→DWG→DXF |

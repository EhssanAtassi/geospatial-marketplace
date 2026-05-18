# GIS and CAD File Formats Reference

Detailed reference for the file formats this plugin handles. Each section covers the format's on-disk shape, how to detect it, what to expect inside, library support, and common gotchas.

## Shapefile (`.shp`)

A Shapefile is **not a single file** — it is a set of related files with a shared base name. Tools must point to the `.shp` file; the others are read alongside it.

### File set

| Extension | Required? | Contents |
|---|---|---|
| `.shp` | Yes | Geometry (binary) |
| `.shx` | Yes | Geometry index |
| `.dbf` | Yes | Attribute table (dBASE IV format) |
| `.prj` | No, but expected | Coordinate reference system in WKT text |
| `.cpg` | No | Character encoding of `.dbf` (e.g. `UTF-8`, `CP1252`) |
| `.sbn`/`.sbx` | No | Spatial index (ESRI-specific) |
| `.qix` | No | Quadtree index (MapServer) |
| `.shp.xml` | No | Metadata |

### Detection

```bash
file parcels.shp                  # "ESRI Shapefile"
hexdump -n 4 parcels.shp          # First 4 bytes: 00 00 27 0A (file code 9994 big-endian)
```

### Python reading

```python
import fiona

with fiona.open("parcels.shp") as src:
    print(src.driver)             # 'ESRI Shapefile'
    print(src.crs)                # CRS dict, e.g. {'init': 'epsg:4326'}
    print(src.crs_wkt)            # WKT string from .prj
    print(src.schema)             # geometry type + properties schema
    print(len(src))               # feature count (fast — uses .shx)
    for feature in src:
        geom = feature['geometry']        # GeoJSON-shaped dict
        props = feature['properties']     # OrderedDict
```

### Gotchas

- **No CRS without `.prj`**: `fiona` returns `crs=None`. Always verify the `.prj` is present; if missing, prompt the user for the source CRS.
- **dBASE field name limit is 10 chars**: Long attribute names are truncated when writing. When reading, accept what's there.
- **dBASE encoding is not standardized**: If `.cpg` is missing and Arabic / Cyrillic / Chinese attribute values appear garbled, force the encoding: `fiona.open(path, encoding='cp1256')` for Arabic, `'cp1251'` for Russian, etc.
- **No native multi-geometry**: A Shapefile holds exactly one geometry type per file (Point, LineString, Polygon, or their Multi* variants). Heterogeneous geometry collections are not representable.
- **2GB limit**: The format predates 64-bit offsets. Files larger than 2GB are corrupt with most readers. Use `.gdb` or `.gpkg` for large datasets.

### Quick file dump

```bash
ogrinfo -al -so parcels.shp       # Summary only
ogrinfo -al parcels.shp           # Full feature dump (huge for big files)
```

---

## ESRI File Geodatabase (`.gdb/`)

A File Geodatabase is **a directory**, not a file. The directory has the `.gdb` extension and contains many internal binary files (`a0000000X.gdbtable`, `gdb`, `timestamps`, etc.). Tools must point to the `.gdb` directory.

### Structure

```
parcels.gdb/                       # Directory
├── a00000001.gdbtable              # Catalog
├── a00000002.gdbtable              # First feature class
├── a00000002.gdbindexes
├── a00000002.gdbtablx
├── ...
└── timestamps                      # ESRI internal
```

A single `.gdb` can hold **many feature classes** (layers), each addressable by name.

### Detection

```bash
test -d parcels.gdb && ls parcels.gdb/*.gdbtable 2>/dev/null | head -1
```

If the directory contains files matching `a00000001.gdbtable`, treat it as a File Geodatabase.

### Python reading

```python
import fiona

# List layers (feature classes) inside the .gdb
layers = fiona.listlayers("parcels.gdb")
print(layers)                     # e.g. ['Parcels', 'Buildings', 'Roads']

# Open a specific layer
with fiona.open("parcels.gdb", layer="Parcels") as src:
    print(src.schema)
    print(len(src))
    for feature in src:
        ...
```

### Gotchas

- **Driver name varies**: The open-source `OpenFileGDB` driver in GDAL ≥ 1.11 handles reading. The proprietary `FileGDB` driver requires the ESRI File GDB API (commercial, restricted). Always prefer `OpenFileGDB`.
- **Write support is limited**: GDAL's `OpenFileGDB` is read-only in older versions and partially writable in newer ones. Do not promise write-back to `.gdb` — convert to PostGIS or GeoPackage for write workflows.
- **Layer names are case-sensitive** in some toolchains. Always echo the exact name as `fiona.listlayers` returns it.
- **Common CRS in cadastral GDBs**: country-specific national grids (e.g. EPSG:32637 for Syria/Iraq/Turkey UTM 37N, EPSG:31984 for Brazilian SIRGAS-2000). Almost never WGS84 lat/lng natively — reprojection is always required for web mapping.

### Quick layer dump

```bash
ogrinfo parcels.gdb                       # List layers
ogrinfo -al -so parcels.gdb Parcels       # Summary of one layer
```

---

## AutoCAD DWG (`.dwg`)

DWG is **AutoCAD's proprietary binary format**. There is no pure-Python reader. The pipeline:

```
.dwg ─[LibreDWG dwg2dxf]─► .dxf ─[ezdxf]─► entities ─[mapper]─► Shapely geometries
```

### Detection

```bash
file site-plan.dwg                # "AutoCAD Drawing" or "Drawing Database"
# DWG version is encoded in first 6 bytes:
# AC1009 = R12
# AC1014 = R14
# AC1015 = R2000
# AC1018 = R2004
# AC1021 = R2007
# AC1024 = R2010
# AC1027 = R2013
# AC1032 = R2018
hexdump -n 6 -C site-plan.dwg | head -1
```

### Conversion (DWG → DXF)

```bash
# Using LibreDWG (open-source, GPL)
dwg2dxf -o /tmp/site-plan.dxf site-plan.dwg

# Using ODA File Converter (free for personal use, restricted commercial)
# Headless mode: ODAFileConverter <in_dir> <out_dir> "ACAD2018" "DXF" "0" "1"
```

LibreDWG handles most drawings up to AutoCAD 2018 format. Newer files (2024+) may fail — fall back to ODA File Converter.

### Then read the DXF (see DXF section below).

### Gotchas

- **CRS is almost never embedded.** Civil 3D and Map 3D drawings have georeferencing info but plain AutoCAD does not. Always require the source CRS from the user.
- **Drawing units may be mm, cm, m, ft, inches.** Read `$INSUNITS` from the DXF header (1=inches, 2=feet, 4=mm, 5=cm, 6=meters, 8=microinches, etc.). Scale coordinates accordingly before treating them as geographic.
- **Paper space vs model space.** Geometry intended for storage lives in **model space**; paper space holds the layout (sheet borders, title block, viewports). Read only model space entities.
- **Layers carry semantic meaning by convention.** Layer names like `PARCELS`, `BUILDINGS`, `ROADS`, `ANNOTATION` indicate what each polygon means. Layer filter is essential to avoid ingesting title-block lines.

---

## AutoCAD DXF (`.dxf`)

DXF is the **interchange format** for DWG — text-based (ASCII) or binary, openly documented by Autodesk. Direct Python support via `ezdxf`.

### Detection

```bash
file site-plan.dxf                # "AutoCAD Drawing Exchange File"
head -2 site-plan.dxf             # ASCII DXF: starts with "  0\nSECTION"
```

### Python reading

```python
import ezdxf
from shapely.geometry import LineString, Polygon, Point

doc = ezdxf.readfile("site-plan.dxf")
msp = doc.modelspace()

# Iterate entities by type
for entity in msp.query("LWPOLYLINE"):
    points = [(p[0], p[1]) for p in entity.get_points()]
    if entity.closed:
        geom = Polygon(points)
    else:
        geom = LineString(points)
    layer = entity.dxf.layer

for entity in msp.query("POINT"):
    geom = Point(entity.dxf.location[:2])
    layer = entity.dxf.layer
```

### Entity → geometry mapping

| DXF entity | Shapely geometry | Notes |
|---|---|---|
| `POINT` | `Point` | Direct |
| `LINE` | `LineString` (2 points) | Direct |
| `LWPOLYLINE` (closed) | `Polygon` | Use exterior ring; no holes |
| `LWPOLYLINE` (open) | `LineString` | Direct |
| `POLYLINE` (legacy 3D) | `LineString` (drop Z) | Drop Z unless 3D target |
| `CIRCLE` | `Polygon` (approximated) | `Point(...).buffer(radius)` with N segments |
| `ARC` | `LineString` (sampled) | Use `ezdxf.math.arc` to sample N points |
| `ELLIPSE` | `LineString` / `Polygon` | Sample along parametric form |
| `SPLINE` | `LineString` (sampled) | Use `ezdxf` flattener |
| `HATCH` | `Polygon` (boundary) | Read outer + inner boundary loops |
| `TEXT` / `MTEXT` | — | Skip (annotation, not geometry) |
| `INSERT` (block reference) | — | Expand only if user requests |
| `DIMENSION` | — | Skip |

### Gotchas

- **Encoding**: DXF files written in non-English locales may have layer names or attributes in CP1256 (Arabic), CP1251 (Cyrillic), Big5 (Chinese Traditional), etc. `ezdxf` auto-detects in most cases.
- **Z coordinates**: Many DXF entities are 3D internally with Z=0. Drop Z before sending to spatial DBs unless the user specifically wants 3D geometry.
- **Coordinate range**: DWG/DXF coordinates can be in millimeters of a survey local origin, producing values like (123456.789, 678910.123). These are NOT lat/lng — they need reprojection.

---

## GeoJSON (`.geojson` / `.json`)

The web-native vector format. Already JSON, already typically EPSG:4326.

### Detection

```bash
file features.geojson             # "JSON data"
jq -r '.type' features.geojson    # "FeatureCollection" or "Feature" or "Geometry"
```

### Python reading

```python
import json
with open("features.geojson") as f:
    fc = json.load(f)
assert fc["type"] == "FeatureCollection"
for feat in fc["features"]:
    geom = feat["geometry"]       # already GeoJSON
    props = feat["properties"]
```

Or via fiona for consistency with the other formats:

```python
import fiona
with fiona.open("features.geojson") as src:
    for feature in src:
        ...
```

### Gotchas

- **CRS field is technically deprecated**. RFC 7946 mandates EPSG:4326 for GeoJSON. Many files in the wild still carry a `crs` field — respect it but assume 4326 when absent.
- **Coordinate order is `[longitude, latitude]`** — universal in GeoJSON. Never swap.
- **Large GeoJSON files (>50MB) crash naive parsers**. Use streaming parsers (`ijson`) for big files; or convert to GeoJSON Text Sequences (`.geojsonl`).

---

## KML / KMZ (`.kml` / `.kmz`)

Google Earth's XML format. KMZ is a ZIP containing a `doc.kml` plus optional resources (images, icons).

### Detection

```bash
file route.kml                    # "XML 1.0 document"
head -2 route.kml                 # contains <kml xmlns="http://www.opengis.net/kml/2.2">
unzip -l route.kmz                # KMZ: contains doc.kml
```

### Python reading

```python
import fiona
with fiona.open("route.kml") as src:
    # fiona uses GDAL's LIBKML driver; treats Placemarks as Features
    for feature in src:
        ...
```

### Gotchas

- **Always EPSG:4326** (KML spec).
- **3D coordinates frequently present** (altitude). Drop Z unless needed.
- **Nested folders / styles**: KML has presentation features (styles, icons, time spans) that don't map to GIS. The fiona driver ignores them.

---

## Quick format-detection cheatsheet

```bash
# Run this on an unknown input
case "$1" in
  *.shp)   echo "Shapefile" ;;
  *.gdb|*.gdb/) echo "ESRI File Geodatabase (directory)" ;;
  *.dwg)   echo "AutoCAD DWG (binary)" ;;
  *.dxf)   echo "AutoCAD DXF" ;;
  *.geojson|*.json) echo "GeoJSON (verify with jq)" ;;
  *.kml)   echo "KML" ;;
  *.kmz)   echo "KMZ (ZIP of KML)" ;;
  *)       file "$1" ;;
esac
```

# Coordinate Reference Systems (CRS) and SRIDs

Every piece of geographic data sits in some coordinate reference system. The CRS defines what the numbers `(x, y)` mean — degrees of latitude/longitude, meters east of a survey origin, feet north of a state plane, etc. Mismatched CRS is the most common cause of "the data is plotted in the wrong place" bugs.

## Core Vocabulary

- **CRS** (Coordinate Reference System) — the full definition: datum + projection + units.
- **SRID** (Spatial Reference System ID) — an integer ID for a CRS, usually an EPSG code.
- **EPSG code** — assigned by the EPSG Geodetic Parameter Dataset, the de facto registry. e.g. `4326`, `32637`.
- **WKT** (Well-Known Text) — a CRS serialized as a parenthesized text expression. What Shapefile `.prj` files contain.
- **PROJ string** — a `+proj=...` flag string used by the underlying PROJ library.

## The Two Important CRS Categories

### Geographic (lat/lng on a sphere)

Coordinates are angles. Units: decimal degrees. Range: latitude `[-90, 90]`, longitude `[-180, 180]`. Distance and area calculations require geodesic math (more expensive).

- **EPSG:4326** — WGS84. The default for GPS, web mapping, MongoDB GeoJSON, PostGIS `geography`. **Use this unless you have a specific reason not to.**
- **EPSG:4269** — NAD83. North America datum. Often shows up in US government datasets. Close to but not identical to 4326; differences are sub-meter on most consumer maps.
- **EPSG:4283** — GDA94. Australian datum.
- **EPSG:4258** — ETRS89. European datum. Close to 4326 within ~1 meter for most of Europe.

### Projected (planar coordinates in meters or feet)

Coordinates are linear distances from an origin. Units: meters (UTM, national grids) or feet (US State Plane). Distance and area calculations are Euclidean (fast, accurate within the projection's valid zone).

- **EPSG:32601 – 32660** — UTM Zone 1N through 60N (Universal Transverse Mercator, northern hemisphere). The `N` zone covers a 6°-wide longitude band. Pick the zone whose central meridian is closest to the data's center.
- **EPSG:32701 – 32760** — UTM Zone 1S through 60S (southern hemisphere).
- **EPSG:25830 – 25839** — ETRS89 UTM zones for Europe.
- **EPSG:31370** — Belgian Lambert 72.
- **EPSG:3857** — Web Mercator (Google/OSM tile rendering). **Do NOT store data in 3857** — it's a display projection only, with severe area distortion near the poles.
- **EPSG:2039 – 2046** — Israeli/Palestinian/Jordanian local grids.
- **EPSG:32636** — UTM Zone 36N (covers Egypt, Sudan, parts of Saudi Arabia).
- **EPSG:32637** — UTM Zone 37N (covers Syria, Iraq, parts of Turkey, parts of Saudi Arabia).
- **EPSG:32638** — UTM Zone 38N (covers Iran, Iraq).

## How to identify the CRS of an input file

```python
import fiona
with fiona.open(path) as src:
    print(src.crs)        # CRS dict: {'init': 'epsg:4326'} or {'proj': 'utm', 'zone': 37, ...}
    print(src.crs_wkt)    # Full WKT — useful for unusual systems
```

If `src.crs` is empty or `None`:

- Shapefile: `.prj` is missing. Check the data's documentation, look at coordinate ranges (clues below), or ask the user.
- DWG/DXF: No CRS in the format. Always ask the user.
- KML/GeoJSON: Assume EPSG:4326.

## Inferring CRS from coordinate ranges

| Coordinate range | Likely CRS |
|---|---|
| x in [-180, 180], y in [-90, 90] | EPSG:4326 (WGS84) or 4269 (NAD83) |
| x in [100000, 900000], y in [0, 10000000] | UTM (some zone) |
| Very large positive values, both x and y in [200000, 800000] | UTM (northern hemisphere zone) |
| Values like (123456.789, 678910.123) | Local survey grid — ask user |
| y in [3000000, 4500000] | Possible UTM zone 36–38 northern hemisphere (Middle East / North Africa) |
| Values around 35-40 (small) | Could be lat/lng in the Mediterranean basin or near-equator UTM scaled down |

## Axis Order: the silent killer

EPSG officially defines the axis order for **EPSG:4326 as `(latitude, longitude)`** — but in practice:

| Library / Format | Order |
|---|---|
| GeoJSON spec | `[longitude, latitude]` |
| MongoDB GeoJSON | `[longitude, latitude]` |
| PostGIS `ST_GeomFromGeoJSON` | `[longitude, latitude]` |
| WKT `POINT(x y)` | `(longitude, latitude)` |
| KML | `<coordinates>longitude,latitude</coordinates>` |
| Shapefile geometry | `(longitude, latitude)` after `.prj` reading |
| **GDAL ≥ 3.0 with `OAMS_TRADITIONAL_GIS_ORDER`** | `(longitude, latitude)` |
| **GDAL ≥ 3.0 default for some drivers (GeoPackage authority axis)** | `(latitude, longitude)` — bites people |
| pyproj 2+ | Configurable; **always set `always_xy=True`** |

### Rule of thumb

**Always write code as `(longitude, latitude)`**. When in doubt, force it:

```python
from pyproj import Transformer
transformer = Transformer.from_crs("EPSG:32637", "EPSG:4326", always_xy=True)
x, y = transformer.transform(easting, northing)
# x is longitude, y is latitude — guaranteed
```

If a user reports "the points are in the Indian Ocean" or "the points are in Antarctica", **axis order is swapped** 99% of the time.

## Reprojection patterns

### One-shot in Python (the right way)

```python
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform

# Source: input file's CRS. Destination: EPSG:4326.
transformer = Transformer.from_crs(
    src_crs,
    "EPSG:4326",
    always_xy=True,
).transform

reprojected_geom = transform(transformer, shape(feature["geometry"]))
feature["geometry"] = mapping(reprojected_geom)
```

### One-shot via ogr2ogr

```bash
ogr2ogr \
  -f GeoJSON \
  -t_srs EPSG:4326 \
  -s_srs EPSG:32637 \
  /tmp/output.geojson \
  input.shp
```

`-s_srs` overrides the source CRS (useful for files with missing `.prj`). `-t_srs` is the target.

### In bulk via fiona + pyproj

```python
import fiona
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform

with fiona.open("input.shp") as src:
    transformer = Transformer.from_crs(src.crs, "EPSG:4326", always_xy=True).transform
    schema = src.schema
    schema["geometry"] = schema["geometry"]  # unchanged

    with fiona.open(
        "/tmp/output.geojson",
        "w",
        driver="GeoJSON",
        crs="EPSG:4326",
        schema=schema,
    ) as dst:
        for feature in src:
            geom = shape(feature["geometry"])
            new_geom = transform(transformer, geom)
            feature["geometry"] = mapping(new_geom)
            dst.write(feature)
```

## When NOT to reproject

If the user is **doing analysis in a local projected CRS** (computing accurate areas in square meters, distances along survey lines, buffers in meters), keep the data in the projected CRS. Reproject only for **storage in MongoDB** (which requires GeoJSON in 4326 for 2dsphere indexes) or **display on web tiles** (which use 3857 but most map libraries handle the reprojection automatically).

For PostGIS, you have two valid choices:

1. **Store in 4326** and compute distances using the `geography` type (geodesic, slower).
2. **Store in a projected CRS** matching the data's location (e.g. EPSG:32637 for Syria) and compute distances using `geometry` (planar, fast). Reproject only when sending to clients.

For wide-area data spanning multiple UTM zones, choice 1 is mandatory.

## EPSG lookup quick reference

```bash
# Look up an EPSG code by name (in epsg-registry.org format)
gdalsrsinfo -e "+proj=utm +zone=37 +datum=WGS84"

# Convert WKT to PROJ string
gdalsrsinfo input.prj

# Find which UTM zone a longitude falls in
python -c "lon=37.5; print(f'EPSG:326{31 + int((lon + 180) / 6) % 60:02d}')"
# For longitude 37.5° E: prints EPSG:32637 (Zone 37 North)
```

## Common CRS mistakes

1. **Storing data in 3857 (Web Mercator)** — areas near the poles are wildly distorted. Use 4326 for storage, 3857 only for rendering.
2. **Mixing geometry SRIDs in one table** — PostGIS spatial joins silently return wrong results when SRIDs differ. Add `CHECK (ST_SRID(geom) = 4326)` to the column.
3. **Reprojecting then forgetting `always_xy=True`** — coordinates end up swapped. Always pass the flag.
4. **Assuming the `.prj` is authoritative** — `.prj` text varies between writers. The same CRS can have several WKT forms. Use `Transformer.from_crs` with the WKT instead of regex-parsing the `.prj`.
5. **Reprojecting tiny features near projection edges** — UTM zones are valid for ±3° around the central meridian. Polygons that cross zone boundaries get distorted. For wide-area data, use a continental CRS (e.g. ETRS89 for Europe) or just stay in 4326.

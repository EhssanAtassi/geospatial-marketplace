# Geospatial Marketplace

Claude Code plugins for GIS and CAD workflows. Ingest, analyze, and reason about spatial data.

## Install

```
/plugin marketplace add EhssanAtassi/geospatial-marketplace
/plugin install gis-to-db@geospatial-marketplace
/reload-plugins
```

## Plugins

### [gis-to-db](./plugins/gis-to-db)

Ingest GIS and CAD files (Shapefile, ESRI File Geodatabase, DWG, DXF) into PostGIS, MongoDB, or MySQL spatial. Scaffold full FastAPI services, generate one-shot CLIs, convert inline, or add a GIS-import feature to an existing app. Includes site-suitability analysis, descriptive statistics, spatial clustering, and before/after diff for GIS datasets.

**10 skills + 1 pre-flight validator agent:**

| Skill | Purpose |
|---|---|
| `gis-formats-reference` | Auto-activating knowledge: formats, CRS, PostGIS, MongoDB, MySQL spatial, GDAL toolbox, real-estate / government / utility / environmental / survey vocabulary. |
| `inspect` | Describe a GIS/CAD file's contents (layers, CRS, geometry, feature count, sample features). Read-only. |
| `convert` | Parse a GIS/CAD file inline and emit PostGIS / MySQL INSERTs or MongoDB documents in chat. |
| `make-cli` | Generate a standalone Python CLI (Typer + geopandas) for per-file ingestion. |
| `scaffold-service` | Generate a production-grade FastAPI ingestion service (API key auth, Arq async jobs, Pytest, Prometheus, Docker). |
| `add-module` | Drop a GIS-import feature into an existing NestJS / FastAPI / Django / Angular / React / Next.js / Vue app. |
| `analyze-site` | Rule-based site suitability scoring. 4 built-in purpose rulesets (airport, residential, commercial, public-facility) plus user-supplied custom YAML. |
| `analyze-stats` | Descriptive statistics for a single layer (distributions, geometry validity, duplicates, outliers). |
| `analyze-patterns` | Spatial pattern analysis for point data (DBSCAN clustering, Clark-Evans nearest-neighbor ratio). |
| `analyze-diff` | Before/after comparison of two GIS layers (added/removed/changed features). |

#### Supported inputs

- Shapefile (`.shp` + `.dbf` + `.shx`)
- ESRI File Geodatabase (`.gdb/` directory)
- AutoCAD DWG (via LibreDWG → DXF → ezdxf pipeline)
- AutoCAD DXF
- GeoJSON, KML/KMZ, GeoPackage

#### Supported database targets

- PostgreSQL + PostGIS — geometry/geography columns, GIST indexes
- MongoDB — embedded GeoJSON + 2dsphere indexes
- MySQL 8 spatial — SRID-aware spatial types, R-tree indexes

#### Prerequisites

- Claude Code (any recent version)
- Either a host Python install with `pip install fiona geopandas ezdxf shapely pyproj scikit-learn pyyaml` + `apt-get install gdal-bin libgdal-dev libredwg-tools`, **or** Docker available locally (the plugin uses `osgeo/gdal:ubuntu-small-3.8.0`).

## Roadmap

This marketplace will grow over time with adjacent plugins:

- **raster-toolkit** (planned) — work with GeoTIFF, NetCDF, raster band math, cloud-optimized GeoTIFFs.
- **geocode** (planned) — address → coordinates and reverse, batch geocoding pipelines.
- **routing** (planned) — shortest path, isochrones, drive-time bands, vehicle routing.

Open an issue if you have a spatial-data workflow you'd like to see automated.

## Status

**v0.1.0** — first release. The `gis-to-db` plugin ships with 3 fully-implemented skills (`gis-formats-reference`, `inspect`, `convert`) plus 4 analysis skills, 3 skeleton skills (`make-cli`, `scaffold-service`, `add-module`) that declare their v0.1 status inline, and the pre-flight validator agent.

## License

MIT

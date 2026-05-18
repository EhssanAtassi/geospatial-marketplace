# gis-to-db

Ingest GIS and CAD files (Shapefile, ESRI File Geodatabase, DWG, DXF) into PostGIS, MongoDB, or MySQL spatial — via Claude Code skills.

Part of the [geospatial-marketplace](../..).

## Install

```
/plugin marketplace add EhssanAtassi/geospatial-marketplace
/plugin install gis-to-db@geospatial-marketplace
/reload-plugins
```

## What this plugin does

Turns the painful "I have a GIS file, get it into the database" problem into a guided, repeatable workflow. Five delivery shapes plus four analysis modes plus a pre-flight validator that runs before every action.

## Skills

| Skill | Purpose | Implementation status |
|---|---|---|
| `gis-formats-reference` | Auto-activating knowledge: formats, CRS, PostGIS, MongoDB, MySQL spatial, GDAL toolbox, real-estate / government / utility / environmental / survey vocabulary. | ✅ Full (7 reference files) |
| `inspect` | Describe a GIS/CAD file's contents (layers, CRS, geometry, feature count, sample features). Read-only. | ✅ Full (Python script + 2 references + example) |
| `convert` | Parse a GIS/CAD file inline and emit PostGIS / MySQL INSERTs or MongoDB documents in chat. | ✅ Full (Python script + 2 references + 2 examples) |
| `analyze-site` | Rule-based site suitability scoring. 4 built-in purpose rulesets (airport, residential, commercial, public-facility) plus user-supplied custom YAML. | ✅ Full (Python script + 4 rulesets + example) |
| `analyze-stats` | Descriptive statistics for a single layer (distributions, geometry validity, duplicates, outliers). | ✅ Full (Python script) |
| `analyze-patterns` | Spatial pattern analysis for point data (DBSCAN clustering, Clark-Evans nearest-neighbor ratio). | ✅ Full (Python script) |
| `analyze-diff` | Before/after comparison of two GIS layers (added/removed/changed features). | ✅ Full (Python script) |
| `make-cli` | Generate a standalone Python CLI (Typer + geopandas) for per-file ingestion. | ⚠ Skeleton — SKILL.md inline rubric; templates in v0.2 |
| `scaffold-service` | Generate a production-grade FastAPI ingestion service (API key auth, Arq async jobs, Pytest, Prometheus, Docker). | ⚠ Skeleton — SKILL.md inline rubric; templates in v0.2 |
| `add-module` | Drop a GIS-import feature into an existing NestJS / FastAPI / Django / Angular / React / Next.js / Vue app. | ⚠ Skeleton — v0.1 supports NestJS+Angular+PostGIS+Leaflet inline; templates in v0.2 |

Plus the `gis-preflight-validator` agent that auto-runs before each action skill (checks GDAL/Docker availability, file headers, CRS, DB connectivity).

## Supported inputs

- Shapefile (`.shp` + `.dbf` + `.shx` + optional `.prj`)
- ESRI File Geodatabase (`.gdb/` directory)
- AutoCAD DWG (via LibreDWG → DXF → ezdxf pipeline)
- AutoCAD DXF
- GeoJSON, KML/KMZ, GeoPackage

## Supported database targets

- **PostgreSQL + PostGIS** — geometry/geography columns, GIST indexes
- **MongoDB** — embedded GeoJSON + 2dsphere indexes
- **MySQL 8 spatial** — SRID-aware spatial types, R-tree indexes

## Quick examples

### Inspect a file

```
/gis-to-db:inspect /data/parcels.shp
```

Reports format, geometry type, CRS, feature count, attribute schema, sample features. Read-only.

### Convert to SQL/MongoDB

```
/gis-to-db:convert /data/parcels.shp --target postgis --table-name parcels --ddl --limit 5
```

Emits PostGIS DDL + first 5 INSERT statements in chat; full file saved to `/tmp/parcels.sql`.

### Site suitability

```
/gis-to-db:analyze-site --location "36.55,33.78" --purpose airport
```

Scores the location against the airport ruleset (terrain, road access, city distance, protected zones, airport proximity, flood risk). Produces a verdict + per-criterion rationale.

### Auto-activating reference

Ask:

> What's the difference between PostGIS geometry and geography?

The `gis-formats-reference` skill activates silently with detailed knowledge.

## Prerequisites

One of:

- **Host install** of Python 3.12 + `pip install fiona geopandas shapely pyproj ezdxf scikit-learn pyyaml` + `apt-get install gdal-bin libgdal-dev libredwg-tools`.
- **Docker** locally — the plugin uses `osgeo/gdal:ubuntu-small-3.8.0` for parsing, so no host install needed.

The validator agent reports missing dependencies and recommends a path forward.

## Configuration

Per-project settings live in `.claude/gis-to-db.local.md`. Copy `assets/gis-to-db.local.md.template` to bootstrap. All fields are optional. Configurable: DB URIs, target SRID, Docker image, DWG defaults (source CRS, layer filter, entity types).

> ⚠ **v0.1 known limitation**: the Python scripts do NOT yet parse this settings file. The template documents what v0.2 will support. For v0.1, pass values via CLI flags on each invocation. The validator agent does read this file for some checks.

## v0.2 roadmap

- Full template-based generators for `make-cli`, `scaffold-service`, `add-module`.
- Real OSM Overpass + SRTM DEM fetchers for `analyze-site` (currently placeholders).
- Slope analysis on DEM (currently a 50/100 neutral placeholder).
- Bulk-mode `--limit 0` for streaming huge files in `convert`.
- **Settings parsing**: scripts read `.claude/gis-to-db.local.md` for project defaults (DB URIs, target SRID, Docker image, DWG defaults).

## License

MIT

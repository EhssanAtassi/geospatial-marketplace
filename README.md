# gis-to-db

Ingest GIS and CAD files (Shapefile, ESRI File Geodatabase, DWG, DXF) into PostGIS, MongoDB, or MySQL spatial — via Claude Code skills.

## What this plugin does

`gis-to-db` is a Claude Code plugin that turns the often-painful "I have a GIS file, get it into the database" problem into a guided, repeatable workflow. It targets four delivery shapes:

| Skill | What it does |
|---|---|
| `/gis-to-db:inspect <file>` | Describe a file's contents (format, CRS, layers, geometry types, feature count, sample attributes) — read-only. |
| `/gis-to-db:convert <file> --target <db>` | Parse the file and print ready-to-execute SQL inserts or MongoDB documents directly in chat. |
| `/gis-to-db:make-cli` | Generate a standalone Python CLI (Typer + geopandas) that you run per file. |
| `/gis-to-db:scaffold-service` | Generate a complete FastAPI ingestion service (auth, async jobs, Pytest, Prometheus, Docker). |
| `/gis-to-db:add-module` | Drop a GIS-import feature into your existing NestJS / FastAPI / Django / Angular / React / Next.js / Vue app. |

Plus an auto-activating reference skill (`gis-formats-reference`) that informs Claude's answers about file formats, CRS, and spatial-DB features without any command needed.

## Supported inputs

- **Shapefile** (`.shp` + `.dbf` + `.shx` + `.prj`)
- **ESRI File Geodatabase** (`.gdb/` directory)
- **AutoCAD DWG** (via LibreDWG → DXF → ezdxf pipeline)
- **AutoCAD DXF** (via ezdxf)

## Supported database targets

- **PostgreSQL + PostGIS** — geometry/geography columns, GIST indexes.
- **MongoDB** — embedded GeoJSON + 2dsphere indexes.
- **MySQL 8 spatial** — SRID-aware spatial types, R-tree indexes.

## Prerequisites

- Claude Code (any recent version).
- One of:
  - Host install of Python 3.12 + `pip install fiona geopandas ezdxf` + `apt-get install gdal-bin libgdal-dev libredwg-tools`.
  - **Recommended**: Docker available locally — the plugin uses `osgeo/gdal:ubuntu-small-3.8.0` for parsing, so no host install needed.

## Configuration

Per-project settings live in `.claude/gis-to-db.local.md`. Copy `assets/gis-to-db.local.md.template` from this plugin to bootstrap. All fields are optional.

## Status

**v0.1.0** — initial release. Local-only; not yet published to a marketplace.

## License

MIT

---
name: scaffold-service
description: This skill should be used when the user asks to "scaffold a GIS ingestion service", "create a GIS upload API", "build a FastAPI service for shapefile/DWG/.gdb ingestion", "generate a geospatial ingestion microservice", or invokes `/gis-to-db:scaffold-service`. Produces a complete, production-grade FastAPI service that accepts GIS/CAD file uploads, parses them via fiona/ezdxf/LibreDWG, reprojects to a target SRID, and writes geometries to PostGIS, MongoDB, or MySQL spatial. Includes API key auth, Pytest tests, Arq async job queue, Prometheus metrics, structured logging, and Docker compose wiring.
argument-hint: [--name service-name] [--db-target postgis|mongo|mysql] [--out-dir ./services] [--target-srid 4326]
allowed-tools: Bash, Read, Write, Edit, Glob
---

# Scaffold a full FastAPI GIS ingestion service

This skill generates a complete, runnable FastAPI service for ingesting GIS and CAD files into a spatial database. The output is production-grade — auth, tests, async jobs, observability, and Docker — not a hello-world.

## When to Use

Invoke when the user wants a standalone service they can deploy. Typical phrasings:

- `/gis-to-db:scaffold-service --name parcels-ingest --db-target postgis`
- "Scaffold a FastAPI service that ingests shapefiles into PostGIS."
- "Create a microservice for uploading DWG files and storing parcels."
- "Build a geospatial ingestion API with async jobs."

## What It Generates

Directory structure under `<out-dir>/<service-name>/`:

```
<service-name>/
├── app/
│   ├── main.py                  # FastAPI app, /upload, /jobs/{id}, /metrics, /health
│   ├── auth.py                  # X-API-Key dependency
│   ├── settings.py              # pydantic-settings, reads from .env
│   ├── db/
│   │   ├── postgis.py           # asyncpg + SQLAlchemy GeoAlchemy2 (if --db-target=postgis)
│   │   ├── mongo.py             # motor (if --db-target=mongo)
│   │   └── mysql.py             # aiomysql (if --db-target=mysql)
│   ├── parsers/
│   │   ├── shapefile.py         # fiona-based reader
│   │   ├── geodatabase.py       # fiona FileGDB driver
│   │   ├── dxf.py               # ezdxf entity-to-geometry mapper
│   │   └── dwg.py               # subprocess LibreDWG dwg2dxf → dxf.py
│   ├── jobs/
│   │   ├── worker.py            # Arq worker
│   │   └── tasks.py             # parse_and_ingest task
│   ├── observability.py         # structlog + Prometheus instrumentation
│   └── schemas.py               # Pydantic models
├── tests/
│   ├── conftest.py
│   ├── data/                    # tiny sample .shp, .geojson fixtures
│   ├── test_upload.py
│   ├── test_parsers.py
│   └── test_integration.py
├── Dockerfile                   # python:3.12-slim + GDAL + LibreDWG
├── docker-compose.yml           # api, worker, redis, db
├── pyproject.toml               # uv/poetry compatible
├── .env.example
├── .dockerignore
├── README.md
└── Makefile                     # make dev / make test / make build
```

## How It Works

1. **Validator agent runs first.** Use the Task tool to invoke `gis-preflight-validator` with `mode=scaffold-service`. The validator confirms the chosen DB target is reachable (if URI is set in settings) and that Docker is available for the build step.
2. **Confirm parameters with the user.** Service name, DB target, target SRID, out-dir. Read defaults from `.claude/gis-to-db.local.md`. Ask only for missing values.
3. **Copy templates from `assets/templates/service/`.** Templates use Jinja-style `{{ var }}` placeholders that the skill substitutes for service name, DB target, target SRID, etc.
4. **Filter generated files by DB target.** Only emit `db/<target>.py`, `parsers/` adapters for the chosen target, and the relevant `docker-compose.yml` service stanza.
5. **Write all files via the Write tool.** Show a tree of what was created.
6. **Offer to run.** Print the commands to start the service (`cd <out-dir>/<service-name> && make dev`), but do not run automatically — the user reviews first.

## Template Variables

Templates expect:

- `SERVICE_NAME` — kebab-case, used for directory and docker-compose service names.
- `DB_TARGET` — `postgis` | `mongo` | `mysql`.
- `TARGET_SRID` — int, default 4326.
- `PYTHON_VERSION` — default `3.12`.
- `INPUT_FORMATS` — list, default `["shapefile", "geodatabase", "dxf", "dwg"]`.

## Implementation Reference

- `assets/templates/service/` — the Jinja-style template tree mirrored above. Treat this as the source of truth for what gets generated.
- `references/db-target-matrix.md` — exactly which files differ between postgis / mongo / mysql modes and the spatial schema each emits.
- `references/arq-pattern.md` — how the Arq worker is wired (entry point, redis URL, task signatures).
- `references/observability.md` — structlog config, Prometheus metric names, /metrics endpoint contract.
- `examples/postgis-output/` — full snapshot of a generated service for PostGIS to verify against.

## Important Constraints

- Never overwrite files in the user's filesystem without confirmation. If `<out-dir>/<service-name>/` exists, ask before proceeding.
- Always include a working `.env.example` and a one-line `make dev` quickstart in the generated README.
- Generated code must pass `ruff check` and `mypy --strict` out of the box. Templates are kept clean.
- All file I/O uses async paths — no blocking calls in request handlers.

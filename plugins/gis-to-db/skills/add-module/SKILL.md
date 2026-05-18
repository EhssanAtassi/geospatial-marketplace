---
name: add-module
description: This skill should be used when the user asks to "add a GIS ingestion feature to my app", "scaffold a DWG upload feature into my NestJS / FastAPI / Django / Angular / React / Next.js / Vue project", "wire shapefile parsing into my existing application", "add a geospatial module to this codebase", or invokes `/gis-to-db:add-module`. Detects the host application stack from manifests (`package.json`, `pyproject.toml`, `angular.json`, `next.config.js`), then scaffolds a complete GIS ingestion feature: a Python FastAPI sidecar service for parsing + a host-language backend module (NestJS / FastAPI / Django) + a frontend component (Angular / React / Next.js / Vue) + docker-compose wiring + tests. The sidecar handles all GIS parsing; the host app stays in its native language.
argument-hint: [--host-dir .] [--db-target postgis|mongo|mysql] [--map-lib leaflet|mapbox|openlayers] [--feature-name gis-import]
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# Add a GIS ingestion feature module to an existing app

> **v0.1 status — design doc only.** Pre-built templates land in v0.2 (Slice C). In v0.1, Claude generates the feature module inline from the specs in this SKILL.md. **v0.1 supports only one stack tuple end-to-end: NestJS backend + Angular frontend + PostGIS + Leaflet map preview.** Other backend/frontend/DB/map-library combinations are documented here but require Claude to extrapolate templates — quality varies. For an existing app on a different stack, generate the Python sidecar first via `scaffold-service` and wire the host module manually.

This skill is the headline use case. It takes an existing application — typically a real-estate, government, or utility platform — and adds a complete "upload a GIS or CAD file, parse it, store it, render it on a map" feature. The plugin handles the dual-language nature (Python for GIS, host language for the app) by generating a Python sidecar and wiring the host backend to call it.

## When to Use

Invoke when the user has an existing project and wants GIS ingestion baked into it:

- `/gis-to-db:add-module --host-dir ~/projects/realestate-platform --db-target postgis`
- "Add a feature to my NestJS app that lets users upload DWG site plans."
- "Wire GIS ingestion into my Django backend."
- "Scaffold a parcel-upload feature into my Next.js project."

## What It Generates

The output depends on what's detected in the host repo. Maximal case (NestJS + Angular monorepo, PostGIS target, Leaflet preview):

```
<host-dir>/
├── services/
│   └── gis-ingest-py/             # NEW Python sidecar
│       ├── app/main.py            # FastAPI /parse endpoint
│       ├── app/parsers/           # fiona / ezdxf / LibreDWG handlers
│       ├── Dockerfile
│       └── pyproject.toml
├── backend/                        # detected NestJS root
│   └── src/gis-import/             # NEW module
│       ├── gis-import.module.ts
│       ├── gis-import.controller.ts
│       ├── gis-import.service.ts   # calls sidecar /parse, writes to TypeORM
│       ├── dto/
│       ├── entities/parcel.entity.ts  # TypeORM entity with spatial column
│       └── gis-import.spec.ts
├── frontend/                       # detected Angular root
│   └── src/app/features/gis-import/  # NEW Angular feature
│       ├── gis-import.module.ts
│       ├── components/
│       │   ├── upload/upload.component.ts
│       │   └── map-preview/map-preview.component.ts  # Leaflet
│       └── services/gis-import.service.ts
├── docker-compose.override.yml     # adds gis-ingest-py service, wires backend env
└── README.GIS-IMPORT.md            # how to run, env vars, troubleshooting
```

## Supported Host Stacks (v0.1)

**Backends** (detected via `package.json` or `pyproject.toml`):

| Stack | Detector | Module shape |
|---|---|---|
| NestJS | `package.json` has `@nestjs/core` | Module + Controller + Service + DTO + TypeORM entity |
| FastAPI | `pyproject.toml` has `fastapi` | Router + Service + Pydantic models + SQLAlchemy (PostGIS) / Beanie (Mongo) |
| Django | `pyproject.toml` has `django` or `manage.py` present | App + Views + Models (django.contrib.gis for PostGIS) + Serializers (DRF) |

**Frontends** (detected via manifests):

| Stack | Detector | Component shape |
|---|---|---|
| Angular | `angular.json` exists | Standalone components, Angular service, RxJS |
| React | `package.json` has `react` without `next` | Function components + hooks |
| Next.js | `next.config.js` or `next` in deps | App-router page + API route + components |
| Vue | `package.json` has `vue` | Composition API SFCs |

If both a backend AND a frontend are detected (monorepo or sibling dirs), scaffold both. If only one, scaffold only that side and emit a placeholder README for the other.

## How It Works

1. **Validator agent runs first.** Use the Task tool to invoke `gis-preflight-validator` with `mode=add-module`. The validator inspects the host directory, identifies the stack(s), checks Docker availability for the sidecar, and reports what will be added.
2. **Prompt for missing parameters.** Confirm: feature name, DB target, map library (Leaflet/Mapbox/OpenLayers/skip). Read defaults from settings.
3. **Detect host stack(s) via Glob + Read.** Parse manifests. If detection is ambiguous (monorepo with multiple backends), ask the user to choose.
4. **Generate sidecar.** Copy `assets/templates/sidecar/` into `<host-dir>/services/gis-ingest-py/` with substitutions.
5. **Generate backend module.** Copy from `assets/templates/backends/<stack>/` into the detected backend root.
6. **Generate frontend component.** Copy from `assets/templates/frontends/<stack>/` into the detected frontend root, with map library variant.
7. **Update docker-compose.** If `docker-compose.yml` exists, generate a `docker-compose.override.yml` adding the sidecar service. If not, create a new compose file.
8. **Wire host imports.** Use Edit to add imports — `AppModule` for NestJS, `INSTALLED_APPS` for Django, `app/router.py` for FastAPI, route registration for Angular/Next/Vue.
9. **Write `README.GIS-IMPORT.md`.** Explain env vars, how to start the sidecar, sample API call.
10. **Offer to run.** Print `docker compose up gis-ingest-py` + the backend dev command. Do not run automatically.

## Implementation Reference

- `assets/templates/sidecar/` — Python FastAPI sidecar (single shared template across all hosts).
- `assets/templates/backends/{nestjs,fastapi,django}/` — backend module templates per stack.
- `assets/templates/frontends/{angular,react,nextjs,vue}/` — frontend templates per stack, each containing leaflet/, mapbox/, openlayers/ subdirs.
- `references/host-detection.md` — exact detection rules: which files to check, what to do on ambiguity, how to find the backend/frontend root in monorepos.
- `references/sidecar-contract.md` — HTTP contract between host backend and sidecar (`POST /parse`, request/response schemas, error codes).
- `references/wiring.md` — exact edits to make in `AppModule.ts`, `settings.py`, `app/__init__.py`, etc.
- `examples/nestjs-angular-monorepo/` — end-to-end example: input host structure + expected output tree.

## Important Constraints

- Never modify host files outside the new feature directory without explicit confirmation. Wiring edits (e.g. adding to `AppModule.ts`) must be shown as a diff first.
- If the host repo is dirty (uncommitted changes), warn the user before generating files.
- The sidecar is always Python — never offer to "port it to Node" or shell out to Docker per request.
- Frontend map components must use the existing host's CSS/styling conventions where detectable (Tailwind classes if Tailwind is installed, vanilla CSS otherwise).
- Backend code must match the host's existing module conventions (e.g. NestJS feature modules in `src/<feature>/`, Django apps in `<project>/<app_name>/`).

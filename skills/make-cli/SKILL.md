---
name: make-cli
description: This skill should be used when the user asks to "create a CLI for GIS ingestion", "generate a one-shot script to import shapefiles", "make a command-line tool that loads DWG files into PostGIS", "write a Python CLI for geodatabase to MongoDB", or invokes `/gis-to-db:make-cli`. Produces a standalone Python CLI built with Typer + geopandas/fiona/ezdxf that takes a GIS or CAD file plus a DB URI and ingests features in one command. Lighter than scaffold-service — no FastAPI, no async jobs, no Docker compose — designed for ad-hoc per-file ingestion runs.
argument-hint: [--name cli-name] [--db-target postgis|mongo|mysql] [--out-dir .] [--target-srid 4326]
allowed-tools: Bash, Read, Write, Edit, Glob
---

# Generate a standalone Python CLI for GIS ingestion

> **v0.1 status — design doc with inline generation rubric.** Pre-built templates land in v0.2. In v0.1, Claude generates the CLI from the specs in this SKILL.md inline. Quality is good but slower per invocation than template-based generation.

This skill produces a single-file (or small-package) Python CLI built with Typer. The CLI takes a GIS/CAD file path and a database URI, then ingests features in one shot. No service to deploy — just a tool to run.

## When to Use

Invoke for ad-hoc, manual, or scripted ingestion workflows that don't need a long-running service:

- `/gis-to-db:make-cli --name ingest-parcels --db-target postgis`
- "Make a CLI tool I can run to ingest shapefiles into PostGIS."
- "Generate a Python script that takes a .gdb and writes to MongoDB."
- "I need a one-off command for ingesting DWG files."

## What It Generates

Two output shapes depending on complexity:

### Shape A — single-file script (default, when only one DB target)

```
<out-dir>/
├── <cli-name>.py            # Typer CLI, all logic inline
├── pyproject.toml           # dependencies pinned
├── README.md
└── .env.example
```

### Shape B — small package (when multiple DB targets requested)

```
<out-dir>/<cli-name>/
├── <cli-name>/
│   ├── __init__.py
│   ├── cli.py               # Typer entry point
│   ├── parsers.py           # fiona/ezdxf/LibreDWG dispatch
│   └── writers/
│       ├── postgis.py
│       ├── mongo.py
│       └── mysql.py
├── pyproject.toml
├── README.md
└── .env.example
```

## CLI Surface

The generated CLI exposes one primary command and a small set of options:

```bash
<cli-name> ingest \
  --input ./parcels.shp \
  --db-uri postgresql://user:pass@host/db \
  --target postgis \
  --target-srid 4326 \
  --layer parcels \
  --table parcels \
  --batch-size 1000 \
  [--dry-run] [--verbose]
```

Plus helper commands:

```bash
<cli-name> inspect ./file.shp        # describe a file (same logic as the inspect skill)
<cli-name> version                   # print version
```

## How It Works

1. **Validator agent runs first.** Invoke `gis-preflight-validator` with `mode=make-cli` to confirm Python + GDAL availability on the user's host (since the CLI will run on their machine, not in Docker by default).
2. **Confirm parameters.** Name, DB target(s), out-dir. Read defaults from settings.
3. **Pick template shape.** Single-file when one DB target, package when multiple.
4. **Copy templates from `assets/templates/cli/`.** Substitute placeholders. Filter writers by chosen targets.
5. **Write files.** Show tree of what was created.
6. **Offer to run.** Print install + first-run commands (`pip install -e . && <cli-name> ingest ...`). Do not run automatically.

## Implementation Reference

- `assets/templates/cli/single-file/` — single-file template (Shape A).
- `assets/templates/cli/package/` — package template (Shape B).
- `references/typer-patterns.md` — Typer command patterns, option types, exit codes used.
- `references/batch-ingestion.md` — chunked reads via `fiona` `BytesCollection`, batched DB writes, progress bars via `rich`.
- `examples/sample-runs.md` — exact commands for ingesting Shapefile / .gdb / DWG into each DB target.

## Important Constraints

- The CLI must NOT require Docker by default — it runs on the user's host Python. If GDAL is missing, the CLI prints clear install instructions and exits non-zero.
- All long-running operations show a progress bar (rich).
- `--dry-run` reads and parses the file but writes nothing to the DB.
- Exit codes: 0 success, 1 user error (bad args, file not found), 2 internal error (parser/DB failure), 3 GDAL missing.
- Generated code must pass `ruff check` out of the box.

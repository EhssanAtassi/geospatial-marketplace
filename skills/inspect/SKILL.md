---
name: inspect
description: This skill should be used when the user asks to "inspect", "describe", "preview", "analyze", or "look inside" a GIS or CAD file (`.shp`, `.gdb`, `.dwg`, `.dxf`, `.geojson`, `.kml`), or asks "what's in this shapefile / geodatabase / DWG", "show me the layers", "what CRS does this use", "how many features", "list the attributes". Invoked as `/gis-to-db:inspect <file> [--json] [--features-sample N]`. Read-only — never writes to the user's filesystem outside `/tmp` and never touches a database.
argument-hint: <path-to-gis-or-cad-file> [--json] [--features-sample N] [--layer LAYER_NAME]
allowed-tools: Bash, Read, Write, Glob
---

# Inspect a GIS or CAD file

This skill produces a structured analysis of a GIS or CAD file — its format, geometry type(s), layers, feature count, CRS, attribute schema, and a small sample of features — without writing anything to a database. It is the safe first step before any ingestion.

## When to Use

Invoke when the user wants to understand a file's contents before deciding how to ingest it. Common phrasings:

- `/gis-to-db:inspect ./parcels.shp`
- `/gis-to-db:inspect /data/cadastre.gdb --json`
- `/gis-to-db:inspect ./site-plan.dwg --features-sample 3`
- "What's in this geodatabase?"
- "Describe the layers and CRS of this shapefile."

## What It Produces

Markdown report (default) or JSON (`--json` flag) covering:

- **File summary** — path, size, format detected, driver used.
- **Layer list** — each layer's name, geometry type, feature count, CRS, attribute columns with types.
- **CRS analysis** — detected EPSG (or "unknown"), whether reprojection to EPSG:4326 will be needed, axis order.
- **Sample features** — up to N features per layer (default 3) showing geometry preview + attribute values.
- **Warnings** — missing CRS, invalid geometries, unsupported entity types (for DWG), extreme coordinate values.

## How It Works

1. **Validator agent runs first.** Invoke the `gis-preflight-validator` agent via the Task tool with `mode=inspect` to confirm the file exists, is readable, and GDAL is available (host or Docker).
2. **Decide execution context.** Prefer the host's Python+GDAL if available; otherwise run inside the configured Docker image (`docker_image` from settings, default `osgeo/gdal:ubuntu-small-3.8.0`).
3. **Run the inspection script.** The skill emits `scripts/gis_inspect.py` to `/tmp/gis_inspect.py` (or mounts it into Docker), then executes it with the file path and flags.
4. **Render the report.** Parse the script's JSON output and render the markdown table (or pass through JSON if `--json`).

## Implementation Reference

- `scripts/gis_inspect.py` — Python inspector using `fiona` (Shapefile, .gdb, GeoJSON, KML), `ezdxf` (DXF), and `LibreDWG dwg2dxf` subprocess (DWG → DXF → ezdxf). Outputs structured JSON.
- `references/output-format.md` — exact schema of the JSON the script produces and the markdown rendering rules.
- `references/dwg-pipeline.md` — DWG handling, layer filtering, entity-type-to-geometry mapping rules.
- `examples/sample-output.md` — example markdown report for a Shapefile and a .gdb.

## Important Constraints

- Never write to the user's filesystem outside `/tmp/`. Inspection is read-only.
- Never connect to a database. This skill describes files, not data.
- Always include "next step" suggestions in the report (`/gis-to-db:convert ...`, `/gis-to-db:scaffold-service ...`) based on what was found.

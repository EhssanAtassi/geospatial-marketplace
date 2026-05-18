---
name: convert
description: This skill should be used when the user asks to "convert this shapefile to SQL", "show me the MongoDB inserts for this geodatabase", "give me the PostGIS DDL for this DWG", "translate this GIS file to JSON I can paste into Mongo", or invokes `/gis-to-db:convert <file>`. Parses a GIS or CAD file inline using fiona/ezdxf/LibreDWG (host or Docker), then prints ready-to-execute SQL inserts (PostGIS or MySQL spatial) or MongoDB documents directly into the chat. Does NOT write to a database — the user can copy the output, review, and run themselves.
argument-hint: <path-to-gis-or-cad-file> [--target postgis|mongo|mysql] [--table-name NAME] [--target-srid 4326] [--limit N] [--ddl]
allowed-tools: Bash, Read, Write, Glob
---

# Convert a GIS / CAD file to inline SQL or MongoDB documents

This skill parses a GIS or CAD file and prints database-ready output directly into the chat: PostGIS / MySQL `INSERT` statements or MongoDB documents. The user reviews, copies, and runs them — no DB connection is opened by the skill itself.

## When to Use

Invoke for quick one-shot conversions, debugging, or generating sample data to paste into a SQL console or `mongosh`:

- `/gis-to-db:convert ./parcels.shp --target postgis --table-name parcels`
- "Convert this geodatabase to MongoDB documents."
- "Show me the PostGIS inserts for the first 10 features of this shapefile."
- "Translate this DWG to SQL."

## What It Produces

The chat output contains, in order:

1. **Summary block** — file path, layer chosen, feature count, source CRS, target CRS, target DB.
2. **DDL block** (optional) — `CREATE TABLE` / `CREATE INDEX` for PostGIS or MySQL, or `db.createCollection` + `createIndex` for MongoDB. Emitted only when the user passes `--ddl` or the validator agent reports the target table does not exist.
3. **Data block** — `INSERT` statements (SQL targets) or `db.collection.insertMany([...])` (MongoDB target). Limited to `--limit N` (default 100) features to keep chat output readable.
4. **"Run this" footer** — a `psql ... < file.sql` / `mongosh ... < file.js` / `mysql ... < file.sql` command the user can run, with the file saved to `/tmp/<table-name>.sql` or `.js`.

## How It Works

1. **Validator agent runs first.** Invoke `gis-preflight-validator` with `mode=convert`. The agent inspects the file, detects CRS, and prompts about reprojection or layer filtering if needed.
2. **Resolve target.** If `--target` is missing, ask the user (PostGIS / MongoDB / MySQL) — do NOT silently default. If `default_db_target` is set in `.claude/gis-to-db.local.md`, use that and confirm.
3. **Run the parser.** Emit `scripts/gis_convert.py` to `/tmp/gis_convert.py` (or mount into Docker), then execute with the file path, target, table name, SRID, and limit.
4. **Capture output.** The script writes the full output to `/tmp/<table-name>.sql` (or `.js` for MongoDB) AND prints the truncated version to stdout.
5. **Format for chat.** Wrap the truncated output in fenced code blocks with the right language hint (`sql` or `javascript`). Show the full-file path in the footer.

## Output Format Rules

- **PostGIS**: `INSERT INTO <table> (geom, <attrs>) VALUES (ST_GeomFromGeoJSON('...'), '...');` — one statement per feature.
- **MySQL spatial**: `INSERT INTO <table> (geom, <attrs>) VALUES (ST_GeomFromGeoJSON('...', 4326), '...');` — note the SRID arg.
- **MongoDB**: `db.<collection>.insertMany([{ "geometry": { "type": "Polygon", "coordinates": [...] }, "properties": { ... } }, ...])` — one array call.
- **Geometry**: always serialized as GeoJSON inside the SQL string (PostGIS/MySQL) or as native GeoJSON in the document (MongoDB). Coordinates always `[lng, lat]` after reprojection to EPSG:4326.

## Implementation Reference

- `scripts/gis_convert.py` — Python converter: fiona/ezdxf inputs → reproject → serialize to SQL/JSON output.
- `references/output-rules.md` — exact formatting rules per DB target (quoting, escaping, geometry serialization, attribute typing).
- `references/ddl-templates.md` — `CREATE TABLE` and index templates for each DB target.
- `examples/shapefile-to-postgis.md` — full example: input file metadata + output SQL.
- `examples/dwg-to-mongo.md` — full example: DWG with layer filter + MongoDB output.

## Important Constraints

- Never open a DB connection. This skill is output-only.
- Output limited to `--limit` features (default 100) in chat. Full output always written to `/tmp/`.
- Always reproject to EPSG:4326 unless `--target-srid` is explicitly set.
- For DWG, prompt for source CRS via the validator agent before parsing.
- For DWG with many layers, prompt for `--layer LAYER_NAME` filter via the validator agent.

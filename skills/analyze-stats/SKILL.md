---
name: analyze-stats
description: This skill should be used when the user asks to "show statistics for this GIS layer", "describe the attribute distributions", "summarize this shapefile", "what's the geometry validity of this dataset", "how many duplicates are in this layer", "histogram of parcel areas", "outliers in this data", "data quality report", or invokes `/gis-to-db:analyze-stats`. Produces descriptive statistics for a GIS layer: attribute distributions (numeric histograms, categorical counts), geometry validity report (invalid / self-intersecting / empty), duplicates by attribute or geometry, area / length distributions, feature count breakdown. Pure read-only analysis on a single layer.
argument-hint: <path-to-gis-file> [--layer NAME] [--attribute NAME] [--json] [--top-n 10]
allowed-tools: Bash, Read, Write, Glob
---

# Descriptive Statistics for a GIS Layer

> **v0.1 status — production-ready.** Reads any GIS layer this plugin supports (Shapefile, .gdb, GeoJSON, KML, DXF post-conversion) and produces a quality + distribution report.

## When to Use

- `/gis-to-db:analyze-stats /data/parcels.shp`
- `/gis-to-db:analyze-stats /data/cadastre.gdb --layer Parcels --attribute area_sqm`
- "What's the distribution of parcel sizes in this dataset?"
- "How many invalid geometries are in this shapefile?"
- "Show me a data-quality report for these parcels."

## What It Produces

Markdown report covering:

- **Summary** — feature count, geometry types breakdown, CRS, bounding box.
- **Geometry validity** — invalid count, self-intersecting, empty, with sample IDs.
- **Duplicate analysis** — by geometry hash, by specified attribute.
- **Attribute distributions** — for each numeric attribute: min/max/mean/median/std/percentiles + histogram. For each categorical: top-N value counts + cardinality.
- **Area / length stats** — when geometries are polygons / lines.
- **Outliers** — features with attribute values >3σ from mean, or with extreme area / length.

## How It Works

1. **Validator agent runs first.** Use Task tool: `gis-preflight-validator` mode `analyze-stats`.
2. **Read with fiona** (Shapefile / .gdb / GeoJSON / KML) or **ezdxf** (DXF/DWG post-conversion).
3. **Per-feature pass**: compute geometry validity, area / length, attribute values; build histograms via numpy.
4. **Render markdown** with tables for each section. JSON output also supported via `--json`.

## Implementation Reference

- `scripts/analyze_stats.py` — the analyzer. Uses fiona + numpy + shapely.
- `examples/parcels-stats.md` — example output for a typical cadastral Shapefile.

## Important Constraints

- Read-only. Never modifies the source file.
- Memory budget: streams features when feature count > 100k; loads in-memory otherwise.
- Numeric histograms use 20 bins by default; categorical reports show top-N values (default 10).
- Geometry hash for duplicate detection uses WKB rounded to 6 decimal places (~10cm at WGS84 equator) to tolerate floating-point noise.

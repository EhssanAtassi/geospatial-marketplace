---
name: analyze-diff
description: This skill should be used when the user asks to "compare these two GIS datasets", "what changed between this cadastre version and that one", "diff these shapefiles", "find added or removed parcels", "before and after comparison", "what features moved", or invokes `/gis-to-db:analyze-diff`. Compares two GIS layers — typically two versions of the same dataset over time — and reports added features, removed features, geometry changes (movement, area drift), and attribute changes per feature. Matches features by an attribute key (e.g. `parcel_id`) or by geometric proximity when no key is supplied.
argument-hint: <old.shp> <new.shp> [--key parcel_id] [--proximity-tolerance 5] [--json]
allowed-tools: Bash, Read, Write, Glob
---

# GIS Diff — Before/After Comparison

> **v0.1 status — production-ready.** Two-way diff with attribute-key or proximity matching.

## When to Use

- `/gis-to-db:analyze-diff /data/cadastre-2019.shp /data/cadastre-2025.shp --key parcel_id`
- `/gis-to-db:analyze-diff /data/before.geojson /data/after.geojson --proximity-tolerance 10`
- "What changed between these two parcel datasets?"
- "Find parcels added or removed in the new survey."
- "Compare the 2019 and 2025 building footprints."

## What It Produces

Markdown report with:

- **Summary** — total features old vs new, count added, count removed, count changed, count unchanged.
- **Added** — features in new not in old (with key + sample attributes).
- **Removed** — features in old not in new.
- **Changed** — features present in both with geometry or attribute differences:
  - Area drift (Δm², percentage)
  - Centroid shift (meters)
  - Attribute deltas per field
- **Stable** — features identical in both (count only, not enumerated).

## How It Works

1. **Validator agent runs first.** Confirm both files exist, same geometry type, same CRS (warns and reprojects if not).
2. **Read both layers via fiona.**
3. **Match features**:
   - If `--key <attr>` supplied: match by attribute equality (preferred; needs stable IDs).
   - Otherwise: match by **proximity** — old features ↔ new features within `--proximity-tolerance` (default 5m, in UTM meters). Greedy match by nearest centroid; unmatched features become Added / Removed.
4. **For each matched pair**: compute geometry delta (area change, centroid shift) and per-attribute equality.
5. **Render markdown** with sortable tables.

## Important Constraints

- Both inputs must have the same geometry type (Polygon vs Polygon, etc.). Mixing is rejected with an error.
- Attribute-key matching is preferred when available — proximity matching is approximate and can mismatch nearby unrelated features.
- Geometric similarity threshold for "unchanged": centroid shift < 0.5m AND area drift < 0.1%. Tighter than this risks false-changes from floating-point noise.
- Default proximity tolerance (5m) is suitable for cadastral data; raise for less precise datasets.

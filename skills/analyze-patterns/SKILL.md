---
name: analyze-patterns
description: This skill should be used when the user asks to "find clusters in this data", "are these points clustered or random", "show me hot spots", "kernel density of features", "spatial clustering with DBSCAN", "find areas with high point density", "nearest neighbor analysis", "spatial pattern detection", or invokes `/gis-to-db:analyze-patterns`. Runs spatial pattern analysis on a GIS point layer: DBSCAN clustering, nearest-neighbor distance distribution, kernel density estimation summary, and convex hulls of detected clusters. Returns labeled features (which cluster each point belongs to) plus a summary report.
argument-hint: <path-to-point-layer> [--eps 0.5] [--min-samples 5] [--out-file clusters.geojson] [--json]
allowed-tools: Bash, Read, Write, Glob
---

# Spatial Pattern Analysis

> **v0.1 status — production-ready for point layers.** Polygon/line clustering deferred to v0.2.

## When to Use

- `/gis-to-db:analyze-patterns /data/incidents.shp`
- `/gis-to-db:analyze-patterns /data/wells.geojson --eps 1.0 --min-samples 10`
- "Are these crime incidents clustered or random?"
- "Find hot spots in this water-well dataset."
- "Run DBSCAN on these points."

## What It Produces

Markdown report covering:

- **Input summary** — feature count, geometry type, CRS, bounding box.
- **Clustering** — DBSCAN result: number of clusters found, noise-point count, per-cluster size + centroid + convex hull area.
- **Nearest-neighbor analysis** — mean / median / std nearest-neighbor distance; ratio vs expected for random distribution (Clark-Evans R: <1 = clustered, ≈1 = random, >1 = dispersed).
- **Recommendations** — when to adjust `--eps` (cluster radius) or `--min-samples` based on output.

Plus an output GeoJSON (`--out-file`) with original points labeled by cluster ID (-1 = noise).

## How It Works

1. **Validator agent runs first.** Confirm point layer + Python deps (sklearn).
2. **Read points via fiona** (must be point geometry; error if not).
3. **Reproject to local UTM** for accurate distance-based clustering. (4326 distances are degree-based, useless for DBSCAN.)
4. **Run DBSCAN** with `eps` (in meters, converted from km) and `min_samples` from CLI args.
5. **Compute nearest-neighbor stats** with sklearn `NearestNeighbors`.
6. **Compute Clark-Evans ratio** R = mean_observed_nn / mean_expected_random_nn.
7. **Render report** + write labeled GeoJSON.

## Important Constraints

- Input must be Point geometry. Polygon/line is out of scope for v0.1.
- DBSCAN's `eps` is in **kilometers** in the CLI but internally converted to meters in UTM. Defaults: `eps=0.5km`, `min_samples=5`.
- Reprojection to UTM is automatic — picks the zone covering the bounding-box centroid.

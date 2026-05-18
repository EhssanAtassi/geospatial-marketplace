---
name: reconstruction-tracker
description: This skill should be used when the user asks to "track reconstruction progress", "compare pre-conflict vs current cadastre", "damage assessment for this area", "find destroyed buildings", "post-conflict reconstruction monitoring", "map damaged parcels", "show reconstruction status", or invokes `/civic-gis:reconstruction-tracker`. Compares a pre-event cadastre baseline (parcels + buildings before conflict / disaster) with a post-event survey or remote-sensing layer, classifies each parcel as intact / damaged / destroyed / rebuilt, and produces a per-parcel status report plus aggregate statistics. Composes on top of gis-to-db:analyze-diff.
argument-hint: --baseline path/to/pre-event.geojson --current path/to/post-event.geojson [--damage-layer path/to/damage.geojson] [--key parcel_id]
allowed-tools: Bash, Read, Write, Glob
---

# Reconstruction Tracker

> **v0.1 status — SKILL.md only. Composes on top of `gis-to-db:analyze-diff` for the parcel-by-parcel comparison primitive. Full Python orchestrator lands in v0.2.**

Compare pre-event cadastre with current state and classify each parcel's status. Used for post-conflict reconstruction planning, disaster recovery, and tracking rebuild progress over time.

## When to Use

- `/civic-gis:reconstruction-tracker --baseline cadastre-2010.geojson --current cadastre-2025.geojson`
- "Compare the pre-war cadastre with the current survey of Homs district A."
- "Find destroyed buildings in this area."
- "Map reconstruction progress over the last year."

## Status Classification

For each parcel matched between baseline and current:

| Status | Definition |
|---|---|
| `intact` | Footprint unchanged, building still standing per damage layer (if supplied) |
| `damaged` | Footprint mostly intact but flagged in damage layer |
| `destroyed` | Footprint missing or <30% of baseline area remaining |
| `rebuilt` | Footprint differs from baseline but a new building exists |
| `vacant` | Parcel exists in baseline but no building in current |
| `new_construction` | Parcel/building in current that was not in baseline |
| `unknown` | Match failed; needs manual review |

## How It Works

1. Validator agent runs first (`civic-preflight-validator`, mode=reconstruction-tracker).
2. Invoke `gis-to-db:analyze-diff` on baseline + current to get added/removed/changed/unchanged feature lists.
3. Optionally overlay a damage-classification layer (from drone survey, satellite analysis, or field assessment). Damage layer features tagged with severity (light/moderate/severe/destroyed) override default classification.
4. Per-parcel: assign one of the 7 status values based on the diff result + damage overlay.
5. Aggregate: counts per status, total area per status, hotspot map (clusters of destroyed parcels).
6. Render markdown report + write per-parcel GeoJSON output for visualization.

## Inputs

- **Baseline GeoJSON** — pre-event cadastre. Each parcel must have a stable `parcel_id`.
- **Current GeoJSON** — recent survey or remote-sensing-derived footprints. Same `parcel_id` schema when possible.
- **Damage layer (optional)** — GeoJSON polygons with `damage_severity` property.

## Output

Markdown report with:
- Summary table: parcel count per status, total area per status, %.
- Top-10 damaged neighborhoods (clusters of destroyed parcels).
- Recommendations: priority zones for restitution/reconstruction.

Plus a per-parcel labeled GeoJSON (`<output_dir>/reconstruction-status.geojson`) for downstream mapping.

## v0.2 Plans

- Pre-built Python orchestrator.
- Integration with UN-Habitat damage classification standards.
- Time-series mode (compare 3+ snapshots to track rebuild velocity).
- Property restitution workflow tying status → displaced-person registry.

---
name: landuse-monitor
description: This skill should be used when the user asks to "monitor land use changes", "detect unauthorized changes in land use", "compare current land use against the master plan", "land use change detection", "flag illegal conversions", "track parcel use over time", "land use compliance monitoring", or invokes `/civic-gis:landuse-monitor`. Periodically compares the current land-use snapshot against an approved master plan AND against the previous snapshot, flags both unauthorized changes (current ≠ master plan) and recent changes (current ≠ previous snapshot). Composes on top of gis-to-db:analyze-diff.
argument-hint: --current path/to/current.geojson --master-plan path/to/master-plan.geojson [--previous path/to/last-snapshot.geojson] [--output ./landuse-report]
allowed-tools: Bash, Read, Write, Glob
---

# Land-Use Change Monitor

> **v0.1 status — SKILL.md only. Composes on top of `gis-to-db:analyze-diff` for the periodic change-detection primitive. Full Python orchestrator + scheduled-run state tracking land in v0.2.**

Compare the current land-use snapshot of a town against two references — the approved master plan AND the previous snapshot — and flag both unauthorized and recent changes.

## When to Use

- `/civic-gis:landuse-monitor --current 2026-may.geojson --master-plan master-2024.geojson --previous 2026-jan.geojson`
- "Detect unauthorized land-use changes since last quarter."
- "Compare current land use against the master plan."
- "Flag illegal conversions in this district."

## What It Reports

Two parallel comparisons:

### 1. Compliance — current vs master plan

For each parcel: does its current land-use match the master plan's designated use?

- `compliant` — current matches master plan
- `violation` — current ≠ master plan AND change is recent (since previous snapshot) → likely unauthorized
- `legacy_nonconforming` — current ≠ master plan but unchanged since previous snapshot → pre-existing nonconforming use

### 2. Drift — current vs previous snapshot

What changed since the last run?

- Parcels that changed use
- Parcels that subdivided / merged
- New parcels (subdivisions, new development)
- Removed parcels (mergers, demolition + replatting)

## How It Works

1. Validator agent runs first (`civic-preflight-validator`, mode=landuse-monitor).
2. Run `gis-to-db:analyze-diff --key parcel_id` on current vs master-plan (compliance check).
3. Run `gis-to-db:analyze-diff --key parcel_id` on current vs previous snapshot (drift check).
4. For each parcel, classify status per the rules above.
5. Aggregate: counts per status, "hot zones" with clusters of violations, top-10 most-changed neighborhoods.
6. Render markdown report + write per-parcel labeled GeoJSON for visualization.
7. Save current snapshot as the "previous" for the next run (if `--persist-state` enabled).

## Master-Plan Input Schema

The master-plan GeoJSON must have a `designated_use` property per parcel:

```json
{
  "type": "Feature",
  "geometry": {...},
  "properties": {
    "parcel_id": "P-001",
    "designated_use": "residential_low_density",
    "master_plan_year": 2024
  }
}
```

The current snapshot must have a comparable `current_use` property.

The skill normalizes use codes via a lookup table (`assets/use-code-mapping.yaml`) so that e.g. `residential` and `residential_low_density` are treated as matches when the master plan is less specific than the current cadastre.

## Output

Markdown report + per-parcel GeoJSON (`<output>/parcels-classified.geojson`) with a `landuse_status` property added.

Run-state stored at `<output>/.state.json` for the next periodic run.

## v0.2 Plans

- Pre-built Python orchestrator that runs as a cron / scheduled task.
- Notification hooks (email / Slack) when violations cross a threshold.
- Use-code mapping library covering common international zoning systems.
- Integration with `civic-gis:permit-check` to suggest whether a violation could be retroactively permitted.

# Example: R-1 Single-Family House Check

End-to-end example of `/civic-gis:permit-check` on a proposed single-family residence in an R-1 zone.

## Input — parcel.geojson

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[36.30, 33.51], [36.301, 33.51], [36.301, 33.511], [36.30, 33.511], [36.30, 33.51]]]
  },
  "properties": {
    "parcel_id": "H-2034-12",
    "area_sqm": 850,
    "jurisdiction": "homs-syria",
    "zone_code": "R-1",
    "overlays": []
  }
}
```

## Input — proposal.json

A 4-story residential building, slightly oversized for R-1:

```json
{
  "use": "residential",
  "stories": 4,
  "height_m": 13.5,
  "footprint_sqm": 320,
  "gross_floor_area_sqm": 1180,
  "setback_front_m": 4.0,
  "setback_side_m": 2.5,
  "setback_rear_m": 5.0,
  "parking_spaces": 6
}
```

## Command

```bash
python permit_check.py \
  --area parcel.geojson \
  --proposal proposal.json
```

(The skill reads `jurisdiction=homs-syria` and `zone_code=R-1` from parcel properties — no flags needed.)

## Derived Values

The script computes before evaluating rules:

| Field | Formula | Value |
|---|---|---|
| `lot_coverage_pct` | 320 / 850 × 100 | 37.6% |
| `open_space_pct` | 100 − 37.6 | 62.4% |
| `FAR` | 1180 / 850 | 1.39 |
| `units` (heuristic) | ceil(1180 / 80) | 15 units |

## Output (markdown report)

```markdown
# Permit Check — H-2034-12 (R-1, homs-syria)

**Ruleset:** R-1 Single-Family Residential
**Source:** `/path/to/plugins/civic-gis/assets/rulesets/R-1.yaml`

## Verdict: **NON-COMPLIANT (4 violations)**

| Rule | Required | Proposed | Status |
|---|---|---|---|
| `allowed_use` | residential, single_family, mixed_use_residential | residential | ✓ PASS |
| `max_height_m` | ≤ 10 | 13.5 | ❌ FAIL |
| | _citation:_ Common R-1: max 10m (≈ 2.5 stories) | | |
| `max_lot_coverage_pct` | ≤ 35 | 37.6 | ❌ FAIL |
| | _citation:_ Common R-1: ≤35% lot coverage | | |
| `max_FAR` | ≤ 0.6 | 1.39 | ❌ FAIL |
| | _citation:_ Common R-1: ≤0.6 floor area ratio | | |
| `min_setback_front_m` | ≥ 5 | 4.0 | ❌ FAIL |
| | _citation:_ Common R-1: ≥5m front setback | | |
| `min_setback_side_m` | ≥ 2 | 2.5 | ✓ PASS |
| `min_setback_rear_m` | ≥ 3 | 5.0 | ✓ PASS |
| `min_parcel_size_sqm` | ≥ 300 | 850 | ✓ PASS |
| `min_open_space_pct` | ≥ 50 | 62.4 | ✓ PASS |
| `min_parking_per_unit` | ≥ 1 per units (15 × 1 = 15.0) | 6 (0.40 per units) | ❌ FAIL |
| | _citation:_ Common R-1: ≥1 parking space per dwelling unit | | |

## Recommendations
- Reduce `height_m` to 10 OR apply for variance.
- Reduce `lot_coverage_pct` to 35 OR apply for variance.
- Reduce `FAR` to 0.6 OR apply for variance.
- Increase `setback_front_m` to 5 OR apply for variance.
- Increase the count side of `min_parking_per_unit` to meet ratio: ≥ 1 per units (15 × 1 = 15.0).

## Authoritative Note

This check is **advisory**. Final permit decisions require review by the relevant regulatory authority. Cite this report's run-id when submitting: `civic-gis-permit-check-2026-05-18T14-32-15Z-H-2034-12`.
```

## What This Tells Us

The proposal as-submitted has **multiple R-1 violations**. The applicant has three realistic paths:

1. **Scale down** to comply with R-1: reduce to ~2 stories, ~300 sqm footprint, 5m front setback, redesign for fewer units.
2. **Apply for variances** for each violated rule. Variance requests get hearings; success depends on local board attitude + comparable precedents.
3. **Request rezoning** of the parcel to R-2 or R-3 if the project genuinely serves a community need for higher density. Long process (months to a year); requires master plan support.

## Custom Ruleset Override

If Homs Municipality's actual R-1 rules differ from the generic starter, drop a custom YAML:

```bash
mkdir -p ~/.claude/civic-gis/rulesets/homs-syria
cp ~/.claude/plugins/cache/geospatial-marketplace/civic-gis/assets/rulesets/R-1.yaml \
   ~/.claude/civic-gis/rulesets/homs-syria/R-1.yaml
# Edit to match Homs Municipality Zoning Code, Article 12
```

The skill auto-discovers `~/.claude/civic-gis/rulesets/homs-syria/R-1.yaml` before falling back to the generic starter.

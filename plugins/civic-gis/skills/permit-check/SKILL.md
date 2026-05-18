---
name: permit-check
description: This skill should be used when the user asks to "check if this project complies with zoning", "validate a building permit application", "does this proposal meet setback requirements", "check zoning rules for site X", "permit compliance check", "is this project allowed in zone Y", or invokes `/civic-gis:permit-check`. Scores a proposed project (location + building parameters) against a jurisdiction's zoning ruleset and reports violations with citations. Rule-based and transparent — produces a per-rule pass/fail report, never a black-box decision.
argument-hint: --area path/to/parcel.geojson  --proposal path/to/proposal.json  [--jurisdiction <name>]  [--zone <code>]
allowed-tools: Bash, Read, Write, Edit, Glob
---

# Permit / Compliance Check

> **v0.1 status — production-ready for 3 starter rulesets (residential-zone, commercial-zone, historic-district). Real jurisdictions can add custom rulesets via YAML in `~/.claude/civic-gis/rulesets/<jurisdiction>/<zone>.yaml`.**

Score a proposed project against zoning rules and emit a per-rule compliance report. Advisory only — final permit decisions remain with regulatory authorities.

## When to Use

- `/civic-gis:permit-check --area parcel.geojson --proposal building.json --jurisdiction homs-syria --zone R-1`
- "Does this proposed 4-story residential building comply with R-1 setbacks?"
- "Check this commercial development against the historic district rules."
- "Permit check this project."

## Inputs

### `--area <geojson>` — the parcel

A GeoJSON Feature or FeatureCollection of the candidate parcel(s):

```json
{
  "type": "Feature",
  "geometry": {"type": "Polygon", "coordinates": [...]},
  "properties": {
    "parcel_id": "H-2034-12",
    "area_sqm": 850,
    "zone_code": "R-1"
  }
}
```

### `--proposal <json>` — the project parameters

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
  "parking_spaces": 6,
  "lot_coverage_pct": 37.6
}
```

### `--jurisdiction <name>` and `--zone <code>` — ruleset selectors

If omitted, the skill reads `parcel.properties.jurisdiction` and `parcel.properties.zone_code`.

## What It Produces

Markdown report:

```markdown
# Permit Check — H-2034-12 (R-1, homs-syria)

## Verdict: **NON-COMPLIANT** (3 violations)

| Rule | Required | Proposed | Status |
|---|---|---|---|
| max_height_m | ≤ 12 | 13.5 | ❌ FAIL |
| max_lot_coverage_pct | ≤ 35 | 37.6 | ❌ FAIL |
| min_setback_front_m | ≥ 5 | 4.0 | ❌ FAIL |
| min_setback_side_m | ≥ 2 | 2.5 | ✓ PASS |
| min_setback_rear_m | ≥ 3 | 5.0 | ✓ PASS |
| max_FAR | ≤ 1.5 | 1.39 | ✓ PASS |
| min_parking | ≥ 1 per unit (4 units) | 6 | ✓ PASS |
| allowed_use | residential, mixed-use | residential | ✓ PASS |

## Recommendations
- Reduce building height to ≤ 12m (lose 1 story) OR apply for a height variance.
- Reduce footprint to ≤ 297.5 sqm (= 35% × 850) OR request lot-coverage variance.
- Move building back 1m from front lot line.

## Authoritative Note
This check is advisory. Final permit decisions require review by the relevant
regulatory authority (Department of Urbanism, Municipality of Homs).
Cite this report's run-id when submitting: `civic-gis-permit-check-2026-05-18-...`.
```

## How It Works

1. **Validator agent runs first** (`civic-preflight-validator`, mode=permit-check). Confirms Python + shapely + pyyaml; verifies the parcel file is valid GeoJSON; checks that the jurisdiction's ruleset exists.
2. **Resolve ruleset**. Lookup order: `--jurisdiction`/`--zone` flags → `parcel.properties.{jurisdiction,zone_code}` → fail with clear error. Ruleset YAML found via:
   - `~/.claude/civic-gis/rulesets/<jurisdiction>/<zone>.yaml` (user-supplied, preferred)
   - `assets/rulesets/<zone>.yaml` (plugin's built-in starter rulesets)
3. **Compute derived values**. Some rule inputs aren't in the proposal directly — compute them: `FAR = gross_floor_area / parcel_area`, `units` (from floor area / typical unit size if not given).
4. **Evaluate each rule**. Six rule types: `min`, `max`, `range`, `allowed_values`, `setback_check`, `custom_python` (advanced).
5. **Render report**. Markdown table with required / proposed / status columns. JSON mode (`--json`) emits structured rule results for downstream automation.

## Ruleset Structure

```yaml
name: R-1 Single-Family Residential
jurisdiction: homs-syria
zone_code: R-1
description: Low-density residential, primarily single-family detached homes.

source: "Homs Municipality Zoning Code, Article 12 (2018 ed.)"
last_updated: "2024-03-15"

rules:
  - name: allowed_use
    type: allowed_values
    field: use
    allowed: [residential, mixed-use]
    citation: "Article 12.1"

  - name: max_height_m
    type: max
    field: height_m
    limit: 12
    citation: "Article 12.3.a"

  - name: max_lot_coverage_pct
    type: max
    field: lot_coverage_pct
    limit: 35
    citation: "Article 12.3.b"

  - name: max_FAR
    type: max
    field: FAR  # computed: gross_floor_area_sqm / parcel.area_sqm
    limit: 1.5
    citation: "Article 12.3.c"

  - name: min_setback_front_m
    type: min
    field: setback_front_m
    limit: 5
    citation: "Article 12.4.a"

  - name: min_setback_side_m
    type: min
    field: setback_side_m
    limit: 2
    citation: "Article 12.4.b"

  - name: min_setback_rear_m
    type: min
    field: setback_rear_m
    limit: 3
    citation: "Article 12.4.c"

  - name: min_parking_per_unit
    type: ratio_min
    field: parking_spaces
    denominator: units
    ratio: 1
    citation: "Article 14.2"
```

## Implementation Reference

- `scripts/permit_check.py` — rule engine. Reads parcel + proposal + ruleset, evaluates each rule, emits report.
- `assets/rulesets/residential-zone.yaml` — starter R-1 ruleset.
- `assets/rulesets/commercial-zone.yaml` — starter C-1 ruleset.
- `assets/rulesets/historic-district.yaml` — historic preservation overlay rules.
- `references/rule-types.md` — detailed rule type catalog (min/max/range/allowed_values/setback_check/custom_python).
- `examples/r1-house-check.md` — full worked example.

## Important Constraints

- **Advisory only, not authoritative.** Every report ends with the "Authoritative Note" reminding users to consult the actual regulatory authority.
- **Citations are required.** Every rule in a ruleset must carry a `citation` field pointing to the source regulation (article, section, page). Reports surface these so violations are auditable.
- **No silent defaults.** If a rule field is missing from the proposal, fail explicitly with "field `<x>` required but not provided," not silently pass.
- **Units must be SI internally.** Proposals in imperial are converted upfront with a `--units imperial` flag.
- **Output formats:** markdown by default, JSON via `--json`. CSV planned for v0.2 for permit-officer workflows.

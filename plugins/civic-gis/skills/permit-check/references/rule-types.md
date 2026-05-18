# Permit-Check Rule Types

Catalog of rule types supported by `permit_check.py` in v0.1, plus design notes for ruleset authors.

## Supported types

### `max` — upper bound

```yaml
- name: max_height_m
  type: max
  field: height_m
  limit: 12
  citation: "..."
```

PASS if `proposal[field] <= limit`. FAIL otherwise. Most common type.

### `min` — lower bound

```yaml
- name: min_setback_front_m
  type: min
  field: setback_front_m
  limit: 5
  citation: "..."
```

PASS if `proposal[field] >= limit`. FAIL otherwise.

### `range` — both bounds

```yaml
- name: parcel_size_band
  type: range
  field: parcel_area_sqm
  min: 300
  max: 2000
  citation: "..."
```

PASS if `min ≤ field ≤ max`. Either bound is optional.

### `allowed_values` — enum

```yaml
- name: allowed_use
  type: allowed_values
  field: use
  allowed: [residential, mixed_use]
  citation: "..."
```

PASS if `proposal[field]` is in the `allowed` list. Use for use-class restrictions, material lists, etc.

### `ratio_min` — proportion check

```yaml
- name: min_parking_per_unit
  type: ratio_min
  field: parking_spaces
  denominator: units
  ratio: 1
  citation: "..."
```

PASS if `proposal[field] / proposal[denominator] >= ratio`. Used for parking minimums, open-space ratios, accessible-units quotas.

### `setback_check` — multi-direction in one rule

```yaml
- name: setbacks
  type: setback_check
  fields:
    front: setback_front_m
    side: setback_side_m
    rear: setback_rear_m
  limits:
    front: 5
    side: 2
    rear: 3
  citation: "..."
```

PASS only if all directional setbacks meet their corresponding limit. Failure detail enumerates the directions that failed.

## Reserved / computed fields

The engine pre-computes these and exposes them to rules:

| Field | Formula | Notes |
|---|---|---|
| `lot_coverage_pct` | `footprint_sqm / parcel_area_sqm × 100` | Only if both fields present |
| `open_space_pct` | `100 − lot_coverage_pct` | Only if `lot_coverage_pct` computable |
| `FAR` | `gross_floor_area_sqm / parcel_area_sqm` | Only if both fields present |
| `units` | `ceil(gross_floor_area_sqm / 80)` | Heuristic — override per ruleset with `unit_size_assumption_sqm` (v0.2) |
| `parcel_area_sqm` | from parcel.properties.area_sqm | Required for the formulas above |

## Authoring guidelines

### Always include citations

Every rule must have a `citation` pointing to the source regulation (article, section, page). Reports surface these so the user can audit violations against the actual code.

Good: `"Article 12.3.a (height limit)"`
Bad: `"city code"`

### Prefer specific types over `custom_python`

`custom_python` is on the v0.2 roadmap as an escape hatch. Avoid in v0.1.

If a rule doesn't fit the existing types, consider whether a derived field could make it expressible:

- "Building must have shadow study if over 10m" → derived field `requires_shadow_study = height_m > 10`, then `allowed_values` rule on that.
- "Setbacks scale with height" → derived fields `required_front_setback = height_m * 0.5`, then `min` against that.

### Don't over-rule

A common mistake is to enforce every zoning provision as a separate rule, including non-binary ones ("design must be sympathetic to surroundings"). Permit-check is for **objective, computable** rules. Subjective design review belongs in a human-led process.

Rules to include:
- Quantitative limits (height, area, setbacks)
- Enumerable choices (use class, material list)
- Ratios (parking, density)

Rules to exclude (handle outside this engine):
- Design quality / aesthetics
- "Compatible with character of neighborhood"
- Discretionary findings ("public benefit shown")

### Test rulesets before deploying

For each new ruleset, draft 3-5 test proposals: a clearly compliant one, a borderline case, and 2-3 with known violations. Run permit_check.py against each and verify the output matches expectations.

### Citation source recommendations

Most authoritative source per jurisdiction:

| Jurisdiction type | Citation format |
|---|---|
| US municipality | `"<City> Code of Ordinances § <chapter>.<section>"` |
| US county | `"<County> Zoning Ordinance Article <n>"` |
| UK | `"<Council> Local Plan Policy <code>"` |
| EU member | `"Plan local d'urbanisme (PLU) Art. <n>"` (FR), `"Bebauungsplan (B-Plan) <city> Anlage <n>"` (DE), etc. |
| MENA | `"<City> Zoning Code (<year>) Article <n>"` |

## Roadmap

- v0.2: `custom_python` escape hatch (with a tightly-scoped sandboxed runner)
- v0.2: Automatic overlay merging (multiple rulesets stacked on one parcel)
- v0.2: Variance prediction (which rules typically grant variances vs not)
- v0.3: Multi-language rule descriptions and citations

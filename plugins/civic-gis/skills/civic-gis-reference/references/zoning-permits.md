# Zoning and Permits Reference

Terminology, formulas, and ruleset patterns for zoning compliance work. Loaded by `civic-gis:permit-check` and any conversation about zoning regulation.

## Core Zoning Concepts

### Use Classifications

Zoning codes group permitted activities by **use class**:

| Use class | Typical sub-classes | Common rules |
|---|---|---|
| **Residential** | R-1 (single-family), R-2 (duplex), R-3 (multi-family), R-4 (high-density) | Low FAR, height limits, parking minimums, setback emphasis |
| **Commercial** | C-1 (neighborhood retail), C-2 (general commercial), C-3 (CBD / downtown) | Mixed-use sometimes permitted, parking, signage rules |
| **Industrial** | I-1 (light industrial), I-2 (heavy industrial) | Buffer requirements, environmental review, often separated from residential |
| **Mixed-use** | MU, M-1 | Combined residential + commercial within one parcel |
| **Institutional / Civic** | P (public), IS (institutional) | Schools, government, hospitals; relaxed FAR/parking |
| **Open space / Agricultural** | OS, A | Conservation, minimal construction allowed |
| **Overlay districts** | Historic-1, Floodplain-Overlay | Add constraints ON TOP of base zoning |

### Setback Rules

Distance the building must be from each lot line:

- **Front setback** — from front lot line (street). Largest, typically 5-10m residential / 3-5m commercial.
- **Side setback** — from side lot lines. 1.5-3m residential typical.
- **Rear setback** — from rear lot line. 3-5m residential typical.
- **Corner-lot rule** — both street-facing sides treated as front setback.

### Density and Bulk Metrics

| Metric | Formula | Typical residential range |
|---|---|---|
| **FAR** (Floor Area Ratio) | `gross_floor_area / parcel_area` | 0.4 (suburban) — 3.0 (urban) |
| **Lot Coverage** | `building_footprint / parcel_area` | 25-50% |
| **Height** | Top of structure (varies whether parapet, eave, ridge counts) | 8-15m residential / 20-60m urban |
| **Density** | Dwelling units per hectare/acre | 5-50 du/ha residential |
| **Open space ratio** | `(parcel_area − footprint) / parcel_area` | 50-75% |

### Computed Fields (commonly derived during permit-check)

```python
FAR = gross_floor_area_sqm / parcel_area_sqm
lot_coverage = (footprint_sqm / parcel_area_sqm) * 100
open_space_pct = ((parcel_area_sqm - footprint_sqm) / parcel_area_sqm) * 100
units = math.ceil(gross_floor_area_sqm / 80)  # avg unit size assumption
required_parking = units * parking_per_unit  # from ruleset
```

## Permit Types

| Type | Triggers | Typical review timeline |
|---|---|---|
| **Building permit** | New construction, structural changes | 4-12 weeks |
| **Use permit / occupancy** | Change of use within existing building | 2-6 weeks |
| **Conditional use permit** | Use allowed only with conditions | 6-16 weeks (hearing) |
| **Variance** | Request exception to specific rule (height, setback) | 8-20 weeks (hearing + decision) |
| **Special-use permit** | Specific uses listed in zoning as needing review | 6-16 weeks |
| **Subdivision plat** | Splitting a parcel into smaller lots | 8-24 weeks |
| **Site plan review** | Larger projects, site layout review | 6-16 weeks |
| **Environmental review** | Above thresholds, environmental impact statement required | 16-52 weeks |

## Ruleset Patterns (for permit-check)

### Simple max/min

```yaml
- name: max_height_m
  type: max
  field: height_m
  limit: 12
  citation: "Article 12.3.a"
```

### Allowed values (enum)

```yaml
- name: allowed_use
  type: allowed_values
  field: use
  allowed: [residential, mixed-use]
  citation: "Article 12.1"
```

### Range check

```yaml
- name: parcel_size
  type: range
  field: parcel_area_sqm
  min: 250
  max: 2000
  citation: "Article 10.5"
```

### Ratio min (for parking, open space)

```yaml
- name: min_parking_per_unit
  type: ratio_min
  field: parking_spaces
  denominator: units
  ratio: 1
  citation: "Article 14.2"
```

### Setback check (multi-direction)

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
  citation: "Article 12.4"
```

### Conditional rule (depends on other fields)

```yaml
- name: max_height_corner_lot
  type: max
  field: height_m
  limit: 8                # stricter for corner lots
  condition: lot_type == "corner"
  citation: "Article 12.3.d (corner-lot override)"
```

### Custom python (escape hatch — use sparingly)

```yaml
- name: solar_exposure_check
  type: custom_python
  function: solar_exposure
  arguments:
    height: height_m
    setback: setback_front_m
  citation: "Article 17.2 (solar-rights ordinance)"
```

## Overlay Districts

Zones can stack — a parcel in **R-2 base zone + Historic-1 overlay + Floodplain-Overlay** must comply with all three. permit-check supports this:

```yaml
# residential-base.yaml — applies to all R-* zones
# Then historic-overlay.yaml adds rules on top
# Then floodplain-overlay.yaml adds rules on top

# Lookup chain:
#   parcel.properties.zone_code = "R-2"
#   parcel.properties.overlays = ["historic-1", "floodplain-overlay"]
# permit-check merges all applicable rulesets, with overlays' rules added last (overlays usually tighten constraints)
```

## Common Pitfalls

1. **Height definition varies.** Some codes measure to top of parapet, some to roof ridge, some to eave. Always cite which.
2. **Lot area = parcel area, not buildable area.** Easements, ROW, and unbuildable slopes don't reduce the "lot area" used in FAR/coverage formulas.
3. **Gross vs net floor area.** Most zoning uses **gross** (includes interior walls, stairs, mechanical). Building codes sometimes use net. Always specify.
4. **Setback measurement.** From the lot line, not the curb. The strip between curb and lot line (ROW) is typically excluded.
5. **Variance ≠ rezoning.** A variance lets one project violate a rule. Rezoning changes the rule for everyone. Different process.
6. **Pre-existing nonconforming uses.** Buildings that violated rules adopted after they were built are usually grandfathered, but can lose status if abandoned or substantially modified.

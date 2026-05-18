# civic-gis

GIS toolkit for municipal government and economic development. Compliance checking, post-conflict reconstruction tracking, cadastral publishing, land-use monitoring — plus investment-attraction tools (town profiles, site matching) for small cities and towns.

Sits on top of [gis-to-db](../gis-to-db) for data primitives; adds civic-domain business logic and rulesets.

Part of the [geospatial-marketplace](../..).

## Install

```
/plugin marketplace add EhssanAtassi/geospatial-marketplace
/plugin install gis-to-db@geospatial-marketplace
/plugin install civic-gis@geospatial-marketplace
/reload-plugins
```

(`gis-to-db` is a dependency — several civic-gis skills delegate to it.)

## What this plugin does

Most municipal GIS work falls into one of two buckets: **enforce rules** (zoning, permits, master-plan compliance) or **attract investment** (pitch the town to outside capital). Existing tools serve one or the other; civic-gis covers both with a coherent set of skills.

Particularly useful for **small cities and towns** that lack a dedicated GIS team — and for **post-conflict reconstruction** contexts where the cadastre needs rebuilding alongside the buildings.

## Skills

| Skill | Purpose | Implementation status |
|---|---|---|
| `civic-gis-reference` | Auto-activating knowledge: zoning systems, cadastral standards (global parcel-ID schemes), civic data sources per region, investment vocabulary, reconstruction frameworks (UN-Habitat, Pinheiro Principles). | ✅ Full (5 reference files) |
| `permit-check` | Score a proposed project against zoning rules. YAML rulesets per jurisdiction; 3 starters bundled (R-1, C-1, historic-district). | ✅ Full (Python rule engine + 3 rulesets + reference + example) |
| `investment-profile` | Generate an investor-ready town profile (demographics, infrastructure, available land, incentives, comparable cities) from user-supplied data. | ✅ Full (Python generator + Tartus example + data-sources reference) |
| `investment-sites` | Match a proposed investment (industry, size, budget) to suitable parcels in a town's inventory. Delegates to `gis-to-db:analyze-site` for scoring. | ⚠ Skeleton — SKILL.md inline rubric; Python orchestrator in v0.2 |
| `reconstruction-tracker` | Compare pre-event cadastre baseline with current survey; classify each parcel as intact/damaged/destroyed/rebuilt. Delegates to `gis-to-db:analyze-diff`. | ⚠ Skeleton |
| `cadastral-publish` | Generate public-facing artifacts (Leaflet map, parcel JSON API, extract PDF template, change log) from an official cadastre with privacy filtering. | ⚠ Skeleton |
| `landuse-monitor` | Periodic land-use change detection. Flag unauthorized changes against approved master plan; report drift since last snapshot. | ⚠ Skeleton |

Plus the `civic-preflight-validator` agent that auto-runs before each action skill (jurisdiction resolution, ruleset lookup, input validation, environment checks).

## Quick examples

### Permit / compliance check

```
/civic-gis:permit-check --area parcel.geojson --proposal building.json --jurisdiction homs-syria --zone R-1
```

Scores a proposed building against the R-1 ruleset. Sample worked example in `skills/permit-check/examples/r1-house-check.md`.

### Investment profile

```
/civic-gis:investment-profile --town "Tartus" --bbox "35.85,34.85,35.95,34.95" --data-dir ./tartus-data
```

Generates a markdown profile (demographics + access + land + economy + why-now + risks + comparable cities). Sample worked example for Tartus in `skills/investment-profile/examples/small-town-profile.md`.

### Auto-activating reference

Ask:

> What's the difference between a building permit and a use permit?

The `civic-gis-reference` skill activates silently with terminology + workflow details.

## Composition with gis-to-db

Most civic-gis skills delegate to `gis-to-db` primitives rather than reimplementing them:

| civic-gis skill | gis-to-db primitives used |
|---|---|
| `permit-check` | `gis-formats-reference` (CRS, formats); rule-engine pattern adapted from `analyze-site` |
| `reconstruction-tracker` | `analyze-diff` for parcel-by-parcel change detection |
| `landuse-monitor` | `analyze-diff` (scheduled runs); `inspect` for new data ingest |
| `cadastral-publish` | `convert` to emit public-facing SQL / GeoJSON |
| `investment-profile` | `analyze-site` for site-suitability factors |
| `investment-sites` | `analyze-site` over candidate parcels filtered by criteria |

## Configuration

Per-project settings live in `.claude/civic-gis.local.md`. Copy `assets/civic-gis.local.md.template` to bootstrap. All fields optional. Configurable: default jurisdiction, custom ruleset paths, language (en/ar/fr), `cadastral-publish` privacy filters, `reconstruction-tracker` baseline year + damage standard.

> ⚠ **v0.1 known limitation**: the Python scripts do NOT yet parse this settings file. The template documents what v0.2 will support. For v0.1, pass values via CLI flags on each invocation (`--jurisdiction`, `--ruleset-dir`, `--language`, etc.). The `civic-preflight-validator` agent reads the file for some checks.

## Custom rulesets

`permit-check` looks for rulesets in this order:

1. `--ruleset-dir` flag
2. `~/.claude/civic-gis/rulesets/<jurisdiction>/<zone>.yaml`
3. Built-in starters in `assets/rulesets/<zone>.yaml`

To codify your municipality's actual zoning code, drop a YAML following the schema in `skills/permit-check/SKILL.md`. Every rule must carry a `citation` field pointing to the source regulation — reports surface these so violations are auditable.

## Important caveats

- **Advisory only, never authoritative.** `permit-check` reports always include an "Authoritative Note" reminding users that final permit decisions are made by humans with regulatory authority.
- **Investment profiles must cite sources + dates.** Undated or unsourced stats are silently dropped by `investment-profile`. This is honest discipline, not a bug.
- **Reconstruction-tracker treats "destroyed" as "awaiting restitution," never "available."** Default behavior aligns with Pinheiro Principles property restitution rights for displaced persons.
- **No silent assumption of jurisdiction.** Parcels must carry a jurisdiction key (in properties or via flag) — civic-gis refuses to apply rules across jurisdictions.

## v0.2 roadmap

- Full Python orchestrators for `investment-sites`, `reconstruction-tracker`, `cadastral-publish`, `landuse-monitor`.
- Real OSM + World Bank auto-fetch for `investment-profile` (replaces v0.1 placeholders).
- Overlay ruleset merging for `permit-check` (R-2 base + historic overlay + floodplain overlay).
- Variance prediction (which rules typically grant variances vs not).
- Notification hooks on `landuse-monitor` violations.
- Multi-language ruleset translations.
- **Settings parsing**: scripts read `.claude/civic-gis.local.md` for project defaults (jurisdiction, ruleset_dir, language, privacy filters, reconstruction baseline year).

## License

MIT

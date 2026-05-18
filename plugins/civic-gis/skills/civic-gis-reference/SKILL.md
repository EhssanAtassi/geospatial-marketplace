---
name: civic-gis-reference
description: This skill should be used when the user discusses municipal or civic GIS work — terms like "zoning ordinance", "setback", "FAR (floor area ratio)", "lot coverage", "building permit", "use permit", "variance", "rezoning", "master plan", "cadastre", "parcel ID", "deed", "title", "land registry", "PIN" (Parcel Identification Number), "tax map", "ROW (right of way)", "easement", "land-use code", "comprehensive plan", "subdivision", "plat", "TIF (tax increment financing)", "opportunity zone", "enterprise zone", "investment incentive", "economic development", "investor profile", "site selection", "small town economic development", "post-conflict reconstruction", "damage assessment", "displaced persons", "property restitution", or asks about civic / municipal / governmental geospatial workflows in any country (US, Europe, MENA, etc.). Provides terminology, data-source references, ruleset patterns, and cross-jurisdiction guidance.
---

# Civic GIS Reference

Reference knowledge for municipal government, urban planning, compliance, and economic development workflows. Auto-activates when the user discusses civic/governmental GIS terminology or asks about jurisdiction-specific compliance, cadastral systems, or investment-attraction work.

## When This Skill Helps

Use this skill's content when answering questions about:

- **Zoning and land-use rules** — interpreting zoning codes, computing setbacks, floor-area ratios, lot coverage, height limits.
- **Cadastral systems** — parcel identification schemes (PIN, APN, deed reference) across countries; land-registry workflows.
- **Permit workflows** — building permits, use permits, variances, special-use permits, environmental review.
- **Civic data sources** — OpenStreetMap, country-specific cadastral portals, census/demographic data, infrastructure layers.
- **Reconstruction and post-conflict work** — damage classifications, property-restitution processes, displaced-persons registration.
- **Economic development** — incentive types (TIF, enterprise zones, opportunity zones), investment vocabulary, small-town pitch strategies.

## Key Reference Files

Detailed content lives in:

- `references/zoning-permits.md` — zoning terminology, setback/FAR/coverage formulas, permit workflow patterns, ruleset structure for `permit-check`.
- `references/cadastral-systems.md` — global parcel-ID schemes (US APN, European PIN, MENA tapu/cadastre), deed structures, registry data formats.
- `references/civic-data-sources.md` — where to get civic GIS data per region (OSM, national portals, INSPIRE, US Census + ACS, country-specific open-data hubs).
- `references/investment-vocab.md` — economic-development terminology, incentive structures, town-profile metrics that investors look for.
- `references/reconstruction-frameworks.md` — UN-Habitat damage classifications, property restitution frameworks (Pinheiro Principles), post-conflict cadastre repair patterns.

## Core Rules

Apply these without loading a reference file:

1. **Permit-check is "advisory + transparent"**, never authoritative. The plugin scores a proposal against codified rules and lists violations with citations. Final permit decisions are always made by humans with regulatory authority.
2. **Cadastral identifiers are not universal** — never assume a `parcel_id` from one jurisdiction matches another. Always carry the jurisdiction key alongside the ID (`{jurisdiction: "homs-syria", parcel_id: "H-2034-12"}`).
3. **Investment profiles must be sourced and dated.** Every demographic / infrastructure stat carries a `source` and `as_of` field. Outdated investment profiles destroy credibility with investors.
4. **Reconstruction trackers need a "pre-event baseline"** — typically the most recent pre-conflict cadastre or remote-sensing image. Without a baseline, "damage" can't be defined.
5. **Land-use monitoring runs on a schedule**, not on-demand. The signal is *changes since the last run*, so the skill must track its own last-run state per jurisdiction.
6. **Different jurisdictions have different number formats** — meters vs feet, decimal-separator, encoding (Arabic numerals vs Indo-Arabic ١٢٣). The plugin always normalizes to SI + UTF-8 internally, formats for display.

## Composition with gis-to-db

`civic-gis` skills delegate to `gis-to-db` for primitive GIS operations:

| civic-gis skill | gis-to-db primitives used |
|---|---|
| `permit-check` | `gis-to-db:gis-formats-reference` (CRS, formats); rule-engine pattern adapted from `gis-to-db:analyze-site` |
| `reconstruction-tracker` | `gis-to-db:analyze-diff` for parcel-by-parcel change detection |
| `landuse-monitor` | `gis-to-db:analyze-diff` (scheduled); `gis-to-db:inspect` for new data ingest |
| `cadastral-publish` | `gis-to-db:convert` to emit public-facing SQL / GeoJSON |
| `investment-profile` | `gis-to-db:analyze-site` for site-suitability factors |
| `investment-sites` | `gis-to-db:analyze-site` over candidate parcels filtered by criteria |

When invoking a civic-gis skill, reference the relevant gis-to-db skill in the output ("data ingested via `gis-to-db:inspect`, rules evaluated via permit-check ruleset").

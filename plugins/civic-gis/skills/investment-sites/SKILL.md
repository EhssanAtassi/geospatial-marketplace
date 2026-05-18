---
name: investment-sites
description: This skill should be used when the user asks to "find suitable sites for this investment", "match a proposed investment to parcels", "where could this factory go in this town", "show me parcels matching these criteria", "site selection for X industry", "investment site matching", or invokes `/civic-gis:investment-sites`. Filters a town's parcel inventory against an investment brief (industry, size, budget, requirements) and returns ranked candidate sites with concrete rationale. Composes on top of gis-to-db's analyze-site rule engine.
argument-hint: --parcels path/to/parcels.geojson --brief path/to/investment-brief.json [--top-n 10] [--jurisdiction <name>]
allowed-tools: Bash, Read, Write, Glob
---

# Investment Site Matching

> **v0.1 status — SKILL.md only. Claude executes from these instructions inline; pre-built Python script lands in v0.2. Composes on top of `gis-to-db:analyze-site` for per-parcel scoring.**

Match a proposed investment (industry, size, budget, infrastructure needs) to candidate parcels in a town's inventory. Returns the top N parcels with scores and rationale.

## When to Use

- `/civic-gis:investment-sites --parcels parcels.geojson --brief brief.json --top-n 5`
- "Find sites for a 5-hectare manufacturing facility in this town."
- "Where could a hotel go given these criteria?"
- "Match this investment proposal to our available land."

## How It Works

1. Validator agent runs first (`civic-preflight-validator`, mode=investment-sites).
2. Read parcel inventory (GeoJSON FeatureCollection — typically the output of `gis-to-db:convert` on the town's cadastre).
3. Read investment brief JSON: industry, required area, required infrastructure, budget range, must-haves, nice-to-haves.
4. Filter parcels by hard requirements (zoning permits the industry, parcel is large enough, parcel is for sale).
5. Score remaining parcels using the appropriate `gis-to-db:analyze-site` ruleset (selected by industry: e.g. industrial → industrial.yaml ruleset).
6. Rank by overall score; return top N with per-criterion rationale.

## Investment Brief Format

```json
{
  "industry": "light_manufacturing",
  "required_area_ha": 5.0,
  "required_infrastructure": ["water", "3_phase_power", "fiber"],
  "must_have": {"distance_to_highway_km": "<= 10"},
  "nice_to_have": {"distance_to_port_km": "<= 50"},
  "budget_usd": 2000000,
  "headcount": 80
}
```

## Output

Markdown report with ranked candidate parcels, per-parcel scores, and a "shortlist" of 2-3 strongly recommended sites.

## v0.2 Plans

- Pre-built Python script that calls `gis-to-db:analyze-site` programmatically.
- Industry-specific ruleset library (light-manufacturing, hospitality, agribusiness, logistics, services).
- Map preview output (Leaflet HTML).

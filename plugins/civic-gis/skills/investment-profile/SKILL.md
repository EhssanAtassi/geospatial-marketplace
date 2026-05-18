---
name: investment-profile
description: This skill should be used when the user asks to "generate an investor profile for this town", "create an economic development pitch", "show investor metrics for city X", "what would investors want to know about this town", "build an investment one-pager", "town profile for site selection", "economic development brief", or invokes `/civic-gis:investment-profile`. Generates an investor-ready profile of a small city or town: demographics, infrastructure, available land, key industries, incentives, comparable cities. Pulls from user-supplied data and free public sources. Outputs markdown, JSON, or a one-page PDF brief.
argument-hint: --town "<name>" --bbox "minLng,minLat,maxLng,maxLat" | --boundary path/to/boundary.geojson  [--data-dir ./data]  [--language en|ar|fr]  [--format markdown|json|pdf]
allowed-tools: Bash, Read, Write, Edit, Glob, WebFetch
---

# Investment Profile

> **v0.1 status — production-ready for user-supplied data; OpenStreetMap auto-fetch is a stub (returns empty layers, neutral scores). Comparable-cities suggestions deferred to v0.2.**

Generate an investor-ready profile of a small city or town. The output is structured to answer the five questions an investor asks first: *Who lives there? How do I get to / from there? What's already there? Where can I build? Why now?*

## When to Use

- `/civic-gis:investment-profile --town "Tartus" --bbox "35.85,34.85,35.95,34.95"`
- `/civic-gis:investment-profile --boundary tartus-boundary.geojson --data-dir ./tartus-data`
- "Create an investor profile for this town."
- "Build an economic development pitch for site X."
- "Show investor metrics for this municipality."

## What It Produces

Markdown report (default) with these sections:

```markdown
# Investment Profile — <Town Name>

## At-a-Glance
- Population: <N>
- Area: <X km²>
- Distance to nearest major city: <Y km>
- Median household income: <Z>
- Primary industries: <list>
- Key incentive: <one-liner>

## 1. People (Demographics)
| Indicator | Value | Source | As-of |
|---|---|---|---|
| Population | ... | ... | ... |
| Working-age (15-64) | ... | ... | ... |
| Education (post-secondary %) | ... | ... | ... |
| Population trend (5y) | ... | ... | ... |

## 2. Access (Infrastructure)
- Highway access: <description, distances>
- Port / airport / rail: <distances and capacities>
- Internet: <available speeds, fiber coverage>
- Water / power / gas: <coverage + reliability notes>

## 3. Land Availability
- Total developable area: <ha>
- Industrial zones: <ha>
- Commercial zones: <ha>
- Residential zones: <ha>
- Average parcel price (sqm): <USD/EUR/SYP>
- Vacant land near existing infrastructure: <ha>

## 4. Existing Economy
- Major employers: <list with sector + headcount>
- Top industries by share: <list with %>
- Recent investments (last 5y): <count, total amount>
- Skilled workforce gaps: <list>

## 5. Why Now (Differentiators)
- Current incentives: <list — TIF zones, tax holidays, training subsidies>
- Recent improvements: <list — completed infrastructure projects>
- Competitive advantages: <list — proximity, cost, talent>
- Risks to flag: <honest list — common ones: regulatory, currency, security>

## Comparable Cities
| Town | Distance | Similar attribute | What worked there |
|---|---|---|---|
| <a> | <km> | <population, industry mix> | <attracted X investment in Y year> |

## Data Sources
- User-supplied: <file list>
- OpenStreetMap (roads, POIs)
- World Bank / national statistics (demographics)
- ...

## Investor Contact
- <Town economic development office contact>
```

JSON mode (`--json`) emits the same structure as machine-readable data. PDF mode (`--format pdf`) calls pandoc to produce a 1-2 page PDF brief suitable for direct distribution.

## How It Works

1. **Validator agent runs first** (`civic-preflight-validator`, mode=investment-profile). Confirms Python + pyyaml + (optional) pandoc-for-PDF; verifies the boundary/bbox is valid.
2. **Resolve boundary**. Either `--boundary` (GeoJSON) or `--bbox` (lng/lat extents). Used to clip all subsequent layers.
3. **Gather demographic data**. Lookup order:
   - User-supplied CSV/JSON in `<data-dir>/demographics.csv` (preferred — most accurate).
   - World Bank API for country-level fallback (population, GDP).
   - National statistics office (jurisdiction-specific; v0.2).
4. **Gather infrastructure layers**. Same lookup order: user-supplied → OSM fetch → flagged as missing.
5. **Compute land-availability stats** from cadastre + zoning layers (user-supplied). Uses `gis-to-db:gis-formats-reference` for format/CRS handling.
6. **Find comparable cities** (v0.2 — placeholder in v0.1). Match by population band + primary industry + region.
7. **Render** report. Sources and as-of dates are mandatory on every stat — outdated profiles destroy credibility.

## Implementation Reference

- `scripts/investment_profile.py` — orchestrator. Reads inputs, gathers layers, computes stats, renders report.
- `references/data-sources.md` — where to get civic data per region (OSM tags, World Bank, INSPIRE, national portals).
- `examples/small-town-profile.md` — full example output for a 50,000-person town.

## Important Constraints

- **Every stat must carry source + as-of.** Investors won't trust undated numbers. Stats with missing source/as-of are dropped from the report (with a warning).
- **No hallucinated comparable cities.** v0.1 leaves the comparable-cities section as a "v0.2" placeholder rather than inventing matches.
- **Multilingual output.** `--language en|ar|fr` switches the report template. Section names and stat labels are translated; data values are not.
- **Honesty about risks.** The "Why Now" section is required to include a "Risks to flag" subsection. Profiles that hide risks erode trust on first contact with sophisticated investors.

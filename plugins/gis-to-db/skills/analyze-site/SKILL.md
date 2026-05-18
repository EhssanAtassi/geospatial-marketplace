---
name: analyze-site
description: This skill should be used when the user asks to "evaluate this location", "is this a good site for X", "site suitability analysis", "why is this location good/bad for an airport / hospital / residential development / factory / solar farm", "score this candidate site", "compare two locations for purpose Y", "site selection criteria", or invokes `/gis-to-db:analyze-site`. The skill scores a candidate point or polygon against a per-purpose ruleset (terrain slope, distance to roads/cities/water, conflict with protected zones, flood risk, demographic context) and produces a transparent markdown report with weighted criteria, scores, and concrete "why" sentences. Rule-based, explainable — no ML, no training data needed.
argument-hint: --location "lng,lat" | --area path/to/polygon.geojson  --purpose airport|residential|commercial|public-facility|<custom>  [--data-dir ./layers]  [--fetch-osm]  [--fetch-dem]
allowed-tools: Bash, Read, Write, Edit, Glob, WebFetch
---

# Site Suitability Analysis

> **v0.1 status — production-ready for 4 built-in purposes (airport, residential, commercial, public-facility) plus user-supplied custom rulesets. Free public data sources (OSM, SRTM DEM, Natural Earth). No satellite imagery yet — that's a v0.2 candidate.**

This skill answers the question "**why is this location good (or bad) for purpose X?**" by overlaying the candidate location against terrain, infrastructure, exclusion zones, and demographic data, then scoring each criterion in a per-purpose ruleset.

The output is a markdown report a human can read and trust — not a black-box number.

## When to Use

Common phrasings that trigger this skill:

- `/gis-to-db:analyze-site --location "36.30,33.51" --purpose airport`
- `/gis-to-db:analyze-site --area parcel.geojson --purpose residential`
- "Is this location good for an airport?"
- "Why would site A be better than site B for a hospital?"
- "Score this candidate site for industrial development."
- "Run site suitability on these coordinates for a solar farm."

## What It Produces

A markdown report with these sections:

```markdown
# Site Suitability — <purpose> at <location>

## Verdict: <RECOMMENDED | CONDITIONAL | NOT RECOMMENDED>  (score: 73 / 100)

## Criteria

| Criterion | Weight | Score | Why |
|---|---|---|---|
| Terrain slope | 20% | 92 | Average slope 1.2°; max 2.8°. Within airport limit (<3°). |
| Distance to nearest city | 15% | 80 | 24 km to Damascus center. Acceptable noise buffer. |
| Distance to major road | 15% | 65 | 8 km to M5 highway. Workable but not ideal. |
| Conflict with protected areas | 25% | 100 | No overlap with Natural Earth protected zones. |
| Flood risk | 10% | 90 | Elevation 612m, not in floodplain. |
| Existing airport proximity | 15% | 40 | 38 km to Damascus International — too close, ATC conflict likely. |

## Recommendations
- Re-evaluate with 60+ km separation from existing airports.
- Acquire detailed local flood-zone GIS to refine flood-risk score.

## Data Sources
- OSM (roads, urban areas, airports)
- SRTM 30m DEM (elevation, slope)
- Natural Earth Protected Areas (admin layer)
- User-supplied: <path-to-user-layers>
```

## How It Works

1. **Validator agent runs first.** Invoke `gis-preflight-validator` with `mode=analyze-site`. Confirms Python + geopandas + rasterio (for DEM) availability. Verifies the location/area input is valid.
2. **Resolve purpose ruleset.** Built-in purposes map to YAML files in `assets/rulesets/`. Custom purposes look in `<data-dir>/.gis-to-db/rulesets/` then `~/.claude/gis-to-db/rulesets/`. Each ruleset defines criteria with weights and thresholds.
3. **Gather reference data.** User-supplied layers first; missing layers fetched from OSM (via Overpass API) and SRTM DEM (via OpenTopography) if `--fetch-osm` / `--fetch-dem` are set. Cached to `./.gis-to-db-cache/` for re-runs.
4. **Reproject to a common CRS.** For local analysis, pick a UTM zone covering the candidate area. For wide-area or unknown, EPSG:4326 with geodesic distances.
5. **Score each criterion.** The script applies the ruleset: distance calculations (shapely + pyproj), terrain stats (rasterio + numpy on DEM), spatial-overlay checks (geopandas .sjoin).
6. **Aggregate score.** Weighted average of criterion scores → overall 0-100 score. Verdict thresholds: ≥70 RECOMMENDED, 50-69 CONDITIONAL, <50 NOT RECOMMENDED (configurable in ruleset).
7. **Render report.** Markdown with table, verdict, recommendations, data-source attribution.

## Ruleset Format

Each purpose is a YAML file. Built-in: `assets/rulesets/{airport,residential,commercial,public-facility}.yaml`. Schema:

```yaml
name: airport
description: Greenfield commercial airport siting criteria.
verdict_thresholds:
  recommended: 70
  conditional: 50

criteria:
  - name: terrain_slope
    weight: 20
    type: terrain_stat
    stat: max_slope_degrees
    score_curve: linear_decreasing
    bounds: { ideal: 0, acceptable: 2, unacceptable: 5 }

  - name: distance_to_nearest_city
    weight: 15
    type: distance_to_layer
    layer: osm:place=city
    score_curve: bell
    bounds: { min: 15, ideal: 30, max: 80 }  # km — too close = noise, too far = unreachable

  - name: distance_to_major_road
    weight: 15
    type: distance_to_layer
    layer: osm:highway=motorway|trunk
    score_curve: linear_decreasing
    bounds: { ideal: 2, acceptable: 15, unacceptable: 50 }  # km

  - name: protected_area_conflict
    weight: 25
    type: overlap_with_layer
    layer: natural_earth:protected_areas
    score: { no_overlap: 100, partial_overlap: 30, full_overlap: 0 }

  - name: existing_airport_proximity
    weight: 15
    type: distance_to_layer
    layer: osm:aeroway=aerodrome
    score_curve: linear_increasing
    bounds: { unacceptable: 0, acceptable: 30, ideal: 80 }

  - name: flood_risk
    weight: 10
    type: terrain_threshold
    stat: elevation_meters
    score_curve: linear_increasing
    bounds: { unacceptable: 0, acceptable: 100, ideal: 500 }
```

### Adding a custom purpose

User drops a YAML at `~/.claude/gis-to-db/rulesets/<name>.yaml` and calls `--purpose <name>`. The skill picks it up automatically. No code changes needed.

## Data Sources (v0.1)

| Source | What it provides | Auth needed | Internet |
|---|---|---|---|
| User-supplied GIS layers | Whatever the user has — parcels, ownership, zoning, etc. | No | No |
| **OSM via Overpass** | Roads, cities, airports, water, land use | No | Yes (`--fetch-osm`) |
| **SRTM 30m DEM via OpenTopography** | Elevation, slope, aspect | No (free public) | Yes (`--fetch-dem`) |
| **Natural Earth** | Protected areas, country boundaries | No | One-time download cached |

## Implementation Reference

- `scripts/analyze_site.py` — main scorer. Reads ruleset YAML, layers, candidate location; produces the report.
- `scripts/data_fetchers.py` — OSM Overpass query helpers, SRTM tile fetcher, Natural Earth loader.
- `references/criteria-types.md` — full list of supported criterion types (`terrain_stat`, `distance_to_layer`, `overlap_with_layer`, `terrain_threshold`, `density_count`) and how each scores.
- `references/scoring-curves.md` — `linear_increasing`, `linear_decreasing`, `bell`, `step`, `binary` curves with formulas and use cases.
- `assets/rulesets/airport.yaml`, `residential.yaml`, `commercial.yaml`, `public-facility.yaml` — built-in purpose definitions.
- `examples/airport-damascus.md` — full worked example (the airport siting case).

## Important Constraints

- **No black-box scoring.** Every criterion produces a number AND a "why" sentence. The report is auditable.
- **Rule-based, not ML.** No training data, no model weights. Adding a purpose is a YAML file, not a retraining pipeline.
- **Free data only in v0.1.** No commercial APIs, no satellite imagery. Adding these is v0.2 work.
- **Coordinate-order rule applies**: all location inputs are `lng,lat` (longitude first), matching MongoDB/GeoJSON convention.
- **Caching is opt-out but on by default.** OSM and DEM downloads cache to `./.gis-to-db-cache/`. Pass `--no-cache` to force re-fetch.

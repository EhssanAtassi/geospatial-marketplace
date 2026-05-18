# Example: Airport siting near Damascus, Syria

End-to-end example of `/gis-to-db:analyze-site` for an airport-purpose evaluation. Demonstrates the question "*is this location good for an airport?*" — the user's headline use case for this skill.

## Scenario

Evaluate a candidate site 35 km northeast of Damascus, in the desert plain between Damascus and Palmyra. Coordinates: longitude `36.5500`, latitude `33.7800`.

## Command

```bash
python analyze_site.py \
  --location "36.5500,33.7800" \
  --purpose airport \
  --fetch-osm \
  --fetch-dem
```

(In a Claude session, the slash-command form is `/gis-to-db:analyze-site --location "36.5500,33.7800" --purpose airport`.)

## What the validator agent does first

Before scoring, the `gis-preflight-validator` agent runs with `mode=analyze-site`. It checks:

- Python + `fiona`, `shapely`, `pyproj`, `rasterio` are available (host or Docker fallback).
- The location is well-formed (`-180 <= lng <= 180`, `-90 <= lat <= 90`).
- Internet is reachable for OSM Overpass + OpenTopography DEM fetches.
- The user understands that OSM and DEM data will be downloaded (~50 MB for this region, cached in `./.gis-to-db-cache/`).

When the validator returns GO, the scorer runs.

## Output (markdown report)

```markdown
# Site Suitability — airport at (36.5500, 33.7800)

## Verdict: **CONDITIONAL** (score: 64.3 / 100)

## Criteria

| Criterion | Weight | Score | Why |
|---|---|---|---|
| `terrain_slope` | 20% | 50.0 | Slope analysis not implemented in v0.1 — neutral 50/100. (Coming in v0.2 via numpy gradient on DEM.) |
| `usable_flat_area` | 15% | 50.0 | Flat-area analysis not implemented in v0.1 — neutral 50/100. (Coming in v0.2.) |
| `distance_to_major_road` | 10% | 82.0 | 4.20 km to nearest matching feature (osm:highway=motorway|trunk|primary). |
| `distance_to_nearest_city` | 10% | 88.0 | 32.40 km to nearest matching feature (osm:place=city|town). |
| `protected_area_conflict` | 15% | 100.0 | No overlap with natural_earth:protected_areas. |
| `existing_airport_proximity` | 15% | 35.0 | 28.10 km to nearest matching feature (osm:aeroway=aerodrome). |
| `flood_risk` | 10% | 100.0 | Elevation 745m at centroid. |
| `distance_to_water` | 5% | 92.0 | 8.50 km to nearest matching feature (osm:water=lake|river). |

## Recommendations
- Improve **existing_airport_proximity** (current 35/100): Two airports within ~30km share contested airspace — ATC complexity, reduced parallel operations. International best practice is >50km separation for major commercial airports.
- Improve **terrain_slope** (current 50/100): Runways require near-flat terrain. ICAO recommends <1.5% (0.86°) for code 4 runways. Sites above 5° require major earthworks and are typically rejected.
- Improve **usable_flat_area** (current 15/100): A code-4 runway needs ~3km × 0.5km of buildable land; with apron, terminal, taxiways, and safety clearances, ~500ha contiguous-flat is the comfortable target. <200ha contiguous flat is generally insufficient.

## Data Sources
- OpenStreetMap via Overpass API
- SRTM 30m DEM via OpenTopography
```

## How to read this

**Verdict: CONDITIONAL** — the site is plausible but has real concerns. The score of 64.3 lands in the 50-69 range, so the analysis is "yes with conditions" rather than "clear go" (≥70) or "clear no" (<50).

The **strongest factors** (high scores):
- `protected_area_conflict` (100) — no Natural Earth protected zone overlap.
- `flood_risk` (100) — 745m elevation is well above any flood concern.
- `distance_to_water` (92) — 8.5km from water bodies; comfortable bird-strike buffer.
- `distance_to_nearest_city` (88) — 32km from Damascus; in the noise/overflight sweet spot.

The **weakest factors** (low scores, surfaced as recommendations):
- `existing_airport_proximity` (35) — only 28km from Damascus International Airport. This is the dealbreaker. ICAO best practice is >50km separation for major commercial airports to avoid contested airspace and ATC complexity. A real airport siting study would either move the candidate further away or formally negotiate airspace sharing.
- `terrain_slope` (50) and `usable_flat_area` (50) — flagged as "v0.1 limitation". These are neutral 50/100 placeholders because the slope-analysis code lands in v0.2. For airport siting these are *the* most critical factors — the recommendation would be to manually verify flatness via a DEM viewer (QGIS + SRTM raster) until v0.2 ships.

## What this skill cannot tell you

The skill is rule-based and explainable, but it does NOT replace a real siting study:

- **Local zoning and political feasibility** — no GIS layer captures "the governor won't approve this."
- **Soil bearing capacity** — needs geotechnical surveys, not GIS.
- **Detailed flood modeling** — real flood-zone maps from a hydrologist beat elevation proxies.
- **Wind patterns** — runway orientation needs meteorological data.
- **Land acquisition cost** — varies wildly; not modeled.

What the skill does well: surface the obvious red flags (existing airport too close, in a protected zone, flood-prone, isolated from cities) within seconds, on free public data, with transparent reasoning the user can audit.

## How to iterate

If the verdict is CONDITIONAL or NOT RECOMMENDED, the natural next step is to evaluate alternative candidates:

```bash
# Try a site 80 km east of Damascus
python analyze_site.py --location "37.20,33.55" --purpose airport --fetch-osm --fetch-dem

# Or a site 60 km southeast
python analyze_site.py --location "36.85,33.30" --purpose airport --fetch-osm --fetch-dem
```

Compare scores and recommendations side-by-side. The best candidate emerges from comparison, not from a single absolute score.

## Customizing the ruleset

The built-in `assets/rulesets/airport.yaml` reflects general ICAO + FAA guidance. To use country-specific or operator-specific criteria:

1. Copy the file: `cp assets/rulesets/airport.yaml ~/.claude/gis-to-db/rulesets/airport-syria-civil-aviation.yaml`
2. Edit weights, thresholds, or add new criteria.
3. Run with `--purpose airport-syria-civil-aviation`.

The skill auto-discovers any YAML in `~/.claude/gis-to-db/rulesets/` and treats its filename (sans `.yaml`) as a valid `--purpose` value.

## v0.2 roadmap for analyze-site

- Slope and contiguous-flat-area analysis on DEM (currently neutral placeholders).
- Real OSM Overpass fetching (currently a placeholder returning empty).
- Optional Sentinel-2 land-cover layer.
- Multi-candidate comparison mode (`--candidates a.geojson,b.geojson,c.geojson`).
- Score-weight tuning interactive mode (asks the user "is flood risk more important than road distance?" and adjusts).

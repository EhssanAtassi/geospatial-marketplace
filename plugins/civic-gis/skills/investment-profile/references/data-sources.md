# Investment Profile Data Sources

Where to get the data needed to produce a credible investment profile. Companion to `civic-gis-reference:civic-data-sources.md` (general) — this file focuses specifically on what `investment-profile` skill needs and how to format it for `--data-dir` ingestion.

## File naming convention

The skill auto-discovers files in `--data-dir` by **filename**:

| Filename | Section it populates |
|---|---|
| `demographics.json` or `demographics.csv` | Section 1: People |
| `infrastructure.json` | Section 2: Access |
| `land.json` | Section 3: Land Availability |
| `economy.json` | Section 4: Existing Economy + Comparable Cities |
| `why_now.json` | Section 5: Why Now + Risks |

All fields are optional within each file. The skill renders what's present; missing sections show a "drop data here" note.

## demographics.json

```json
{
  "source": "Syria Central Bureau of Statistics, 2010 Census (most recent pre-conflict)",
  "as_of": "2010",
  "population": 200000,
  "working_age_pct": 62,
  "post_secondary_pct": 28,
  "population_5y_change": -15,
  "median_income": 480,
  "median_income_currency": "USD/month",
  "unemployment_pct": 22,
  "average_wage": 350
}
```

**Sourcing tips:**

- National statistics offices are most authoritative but often lag 2-5 years.
- For small towns, sometimes only governorate/province-level data exists; flag this in `source`.
- World Bank has country-level fallbacks: see civic-gis-reference for indicator codes.
- Post-conflict regions: explicitly cite the pre-conflict baseline year. Honesty beats false precision.

CSV alternative — useful when you have multiple snapshots:

```csv
year,population,working_age_pct,unemployment_pct,source,as_of
2005,210000,60,15,"CBS",2005
2010,200000,62,22,"CBS",2010
2020,140000,58,40,"UN OCHA estimate",2020
```

## infrastructure.json

```json
{
  "source": "OpenStreetMap + Ministry of Public Works",
  "as_of": "2024-Q3",
  "highway_distance_km": 2.5,
  "port_distance_km": 65,
  "airport_distance_km": 145,
  "rail_distance_km": 8,
  "broadband_max_mbps": 50,
  "power_reliability": "8-12h/day grid + 12h+ generators",
  "water_coverage_pct": 85,
  "gas_available": false
}
```

**Sourcing tips:**

- Highway/port/airport distances: measure from town center to nearest. OSM Overpass query can compute these (v0.2 will auto-fetch).
- Broadband: ITU / TeleGeography for country-level, local ISPs for town-level.
- Power: utility company reports + on-the-ground knowledge. Be honest about reliability — investors verify.

## land.json

```json
{
  "source": "Cadastre 2025-Q2 + zoning overlay",
  "as_of": "2025-06",
  "total_developable_ha": 320,
  "industrial_ha": 75,
  "commercial_ha": 45,
  "residential_ha": 200,
  "industrial_price_per_sqm": 25,
  "industrial_price_currency": "USD",
  "vacant_serviced_ha": 18,
  "available_parcels_count": 23,
  "largest_available_parcel_ha": 8.5
}
```

**Sourcing tips:**

- Use `gis-to-db:convert` to ingest the cadastre + zoning, then run aggregate queries to fill this file.
- "Vacant serviced" (utilities at the curb) is the most investor-relevant number — much more so than total available area.
- Average price should be transaction-derived, not asking prices. Asking prices in small towns are usually 30-50% above closing prices.

## economy.json

```json
{
  "source": "Chamber of Commerce + Ministry of Industry",
  "as_of": "2024",
  "major_employers": [
    {"name": "Tartus Refinery", "sector": "Petrochemical", "headcount": 1200},
    {"name": "Port Authority", "sector": "Logistics", "headcount": 800},
    {"name": "Agribusiness Co-op", "sector": "Agriculture", "headcount": 450}
  ],
  "top_industries": [
    {"industry": "Petrochemical", "share_pct": 28},
    {"industry": "Maritime/logistics", "share_pct": 22},
    {"industry": "Agriculture", "share_pct": 18},
    {"industry": "Tourism", "share_pct": 12},
    {"industry": "Light manufacturing", "share_pct": 10}
  ],
  "recent_investments": {
    "count_5y": 7,
    "total_5y_usd": 45000000
  },
  "comparable_cities": [
    {
      "name": "Latakia",
      "distance_km": 90,
      "similar_to": "Coastal port city, similar industry mix",
      "what_worked": "Attracted Russian + Iranian shipping investment 2018-2024"
    },
    {
      "name": "Mersin (Turkey)",
      "distance_km": 380,
      "similar_to": "Port + petrochemical + agribusiness",
      "what_worked": "Free zone + tax holidays attracted European logistics chains"
    }
  ]
}
```

**Sourcing tips:**

- Major employers: chamber of commerce, business registries, news archives.
- "Comparable cities" is optional but powerful. Pick 2-3 cities that an investor would believe are peers, and cite what investment activity they actually attracted.
- Don't invent investments. Investors will fact-check.

## why_now.json

```json
{
  "source": "Municipal economic development office",
  "as_of": "2025-Q1",
  "incentives": [
    "Free Zone status (50km radius around port) — 0% corporate tax for first 10 years",
    "Customs duty exemption on imported industrial equipment",
    "Workforce training subsidy: 50% of training costs for new hires (up to $2000/employee)",
    "Land lease at $1/m²/year for industrial sites with >50 jobs commitment"
  ],
  "recent_improvements": [
    "Highway M-1 widened to 4 lanes (completed 2024)",
    "Port container terminal expansion (450,000 → 800,000 TEU/year, completed 2024)",
    "Fiber optic backbone connection (50 Gbps, completed 2025-Q1)",
    "New 132kV substation (2024)"
  ],
  "advantages": [
    "Deep-water port with year-round operation (no ice, minimal storms)",
    "Free Zone offers fastest customs clearance in the region",
    "Skilled workforce in petrochemical + maritime (historic specialization)",
    "Cost of skilled labor 60% lower than Mediterranean European ports"
  ],
  "risks": [
    "Currency volatility — Syrian Pound has lost 95% of value since 2011",
    "Sanctions exposure — investors must screen partners against OFAC/EU/UK lists",
    "Insurance availability limited — MIGA political risk insurance available, commercial insurance scarce",
    "Banking corresponding-bank relationships strained — settlement may require third-country intermediary"
  ]
}
```

**Sourcing tips:**

- **Be honest about risks.** A profile without a `risks` section is dismissed by sophisticated investors as a brochure rather than a serious document.
- Cite the source of incentive claims. "Tax holiday under Investment Law 8/2007" is auditable; "tax holidays available" is not.
- "Recent improvements" should be specific, completed (not planned), and verifiable. Hyperbole here hurts trust.

## Where to source by region

### MENA / Arab world

- **Country statistics offices**: most have English-language pages now.
- **Arab Investment & Export Credit Guarantee Corporation (Dhaman)** — has country investment profiles.
- **UNCTAD investment policy reviews** — country-level investment climate.
- **Chambers of commerce** — local + Arab chambers.

### Africa

- **African Development Bank** — investment climate per country.
- **AfricaGeoPortal** — geo data.
- **Africa Trade Insurance Agency** — political risk insurance + investment data.

### Europe (smaller cities)

- **Eurostat** — comparable data across countries.
- **Local development agencies** (EU-funded LEADER, INTERREG projects) often publish town-level data.

### Latin America

- **CEPAL (UN Economic Commission)** — comparable data.
- **BID (Inter-American Development Bank)** — project-level investment data.

## Open-data fetcher (v0.2 plan)

In v0.2, the skill will auto-fetch these layers when not user-supplied:

1. **OpenStreetMap (Overpass)** — roads, ports, airports, rail, POIs for infrastructure section.
2. **World Bank country API** — population, GDP, unemployment fallback.
3. **OECD** — for OECD-member countries, more granular fallback.

For v0.1, the skill renders a "drop data here" prompt with the exact filename and field structure expected.

## Multilingual support

For `--language ar` and `--language fr`, section titles and stat labels are translated. Numeric values are not — they remain as supplied. Sources stay in their original language to preserve attribution.

Translation tables in v0.2 will be per-language YAML files; v0.1 ships English only.

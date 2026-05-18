# Example: Tartus Investment Profile

End-to-end example: generating an investor profile for Tartus, Syria — a coastal port city of ~200,000 with deepwater port, petrochemical history, and reconstruction-era investment-attraction needs.

## Input data layout

```
tartus-data/
├── demographics.json
├── infrastructure.json
├── land.json
├── economy.json
└── why_now.json
```

Each file follows the schema in `references/data-sources.md`.

## Command

```bash
python investment_profile.py \
  --town "Tartus" \
  --bbox "35.85,34.85,35.95,34.95" \
  --data-dir ./tartus-data \
  --language en \
  --format markdown
```

## Output (excerpted)

```markdown
# Investment Profile — Tartus

_Generated 2026-05-18 11:42 UTC (language: en)_
_Boundary source: 35.85,34.85,35.95,34.95_

---

## At-a-Glance

- **Population**: 200000 people  *(source: Syria Central Bureau of Statistics, 2010 Census, as of 2010)*
- **Industrial-zoned land**: 75 ha  *(source: Cadastre 2025-Q2 + zoning overlay, as of 2025-06)*
- **Distance to highway**: 2.5 km  *(source: OpenStreetMap + Ministry of Public Works, as of 2024-Q3)*

## 1. People (Demographics)

| Indicator | Value | Source | As-of |
|---|---|---|---|
| Population | 200000 people | Syria Central Bureau of Statistics, 2010 Census | 2010 |
| Working-age (15-64) % | 62 % | Syria CBS | 2010 |
| Post-secondary education % | 28 % | Syria CBS | 2010 |
| Population trend (5y) | -15 % | UN OCHA estimate | 2020 |
| Median household income | 480 | Syria CBS | 2010 |
| Unemployment rate | 22 % | Syria CBS | 2010 |

## 2. Access (Infrastructure)

| Indicator | Value | Source | As-of |
|---|---|---|---|
| Distance to highway | 2.5 km | OSM + MPW | 2024-Q3 |
| Distance to nearest port | 65 km | OSM + MPW | 2024-Q3 |
| Distance to nearest airport | 145 km | OSM + MPW | 2024-Q3 |
| Distance to nearest rail station | 8 km | OSM + MPW | 2024-Q3 |
| Broadband availability | 50 Mbps | OSM + MPW | 2024-Q3 |
| Power grid reliability | 8-12h/day grid + 12h+ generators | OSM + MPW | 2024-Q3 |
| Water grid coverage | 85 % | OSM + MPW | 2024-Q3 |

## 3. Land Availability

| Indicator | Value | Source | As-of |
|---|---|---|---|
| Total developable area | 320 ha | Cadastre 2025-Q2 | 2025-06 |
| Industrial-zoned land | 75 ha | Cadastre 2025-Q2 | 2025-06 |
| Commercial-zoned land | 45 ha | Cadastre 2025-Q2 | 2025-06 |
| Residential-zoned land | 200 ha | Cadastre 2025-Q2 | 2025-06 |
| Average price (industrial) | 25 /m² | Cadastre 2025-Q2 | 2025-06 |
| Vacant land near infrastructure | 18 ha | Cadastre 2025-Q2 | 2025-06 |

## 4. Existing Economy

**Major employers:** Tartus Refinery (Petrochemical, 1200 employees), Port Authority (Logistics, 800 employees), Agribusiness Co-op (Agriculture, 450 employees)

**Top industries (by employment):** Petrochemical (28%), Maritime/logistics (22%), Agriculture (18%), Tourism (12%), Light manufacturing (10%)

| Indicator | Value | Source | As-of |
|---|---|---|---|
| Recent investments (last 5y) | 7 | Chamber of Commerce + Ministry of Industry | 2024 |
| Total amount invested (last 5y) | 45000000 USD | Chamber + MoI | 2024 |

## 5. Why Now

**Current incentives:**
- Free Zone status (50km radius around port) — 0% corporate tax for first 10 years
- Customs duty exemption on imported industrial equipment
- Workforce training subsidy: 50% of training costs for new hires (up to $2000/employee)
- Land lease at $1/m²/year for industrial sites with >50 jobs commitment

**Recent improvements:**
- Highway M-1 widened to 4 lanes (completed 2024)
- Port container terminal expansion (450,000 → 800,000 TEU/year, completed 2024)
- Fiber optic backbone connection (50 Gbps, completed 2025-Q1)
- New 132kV substation (2024)

**Competitive advantages:**
- Deep-water port with year-round operation (no ice, minimal storms)
- Free Zone offers fastest customs clearance in the region
- Skilled workforce in petrochemical + maritime (historic specialization)
- Cost of skilled labor 60% lower than Mediterranean European ports

## Risks to Flag

- Currency volatility — Syrian Pound has lost 95% of value since 2011
- Sanctions exposure — investors must screen partners against OFAC/EU/UK lists
- Insurance availability limited — MIGA political risk insurance available, commercial insurance scarce
- Banking corresponding-bank relationships strained — settlement may require third-country intermediary

## Comparable Cities

| Town | Distance | Similar attribute | What worked |
|---|---|---|---|
| Latakia | 90 km | Coastal port city, similar industry mix | Attracted Russian + Iranian shipping investment 2018-2024 |
| Mersin (Turkey) | 380 km | Port + petrochemical + agribusiness | Free zone + tax holidays attracted European logistics chains |

## Data Sources
- User-supplied: `./tartus-data`
```

## What makes this profile credible

1. **Every stat carries source + date.** No undated numbers.
2. **Demographic data honestly flagged as pre-conflict (2010).** Modern displaced-population estimate cited where available.
3. **Risks section is real and specific.** Currency, sanctions, insurance, banking — the four risks every investor in Syria-context worries about. Naming them lowers the temperature on the first investor call.
4. **Comparable cities are auditable.** Investors can fact-check "Mersin attracted European logistics chains" against public news.
5. **Recent improvements are completed, dated, and verifiable.** Not "planned" or "under consideration."

## What would NOT belong here

- "The next Dubai" — hyperbole.
- "Population: ~250k" — undated and rounded.
- "Tax-free environment" without citing the specific law/decree.
- Comparable city = "London" — implausible peer.
- No risks section — instant red flag.

## Workflow integration

This skill pairs naturally with:

- `gis-to-db:convert` — ingest cadastre + zoning into a queryable DB, then aggregate into `land.json`.
- `civic-gis:investment-sites` — once profile is generated, prospects use this to find specific parcels matching their criteria.
- `civic-gis:permit-check` — once an investor picks a site + use, validate compliance with local zoning.

A typical engagement runs: profile → sites → permit-check, narrowing from "is this town suitable" → "is this site suitable" → "is this proposal compliant."

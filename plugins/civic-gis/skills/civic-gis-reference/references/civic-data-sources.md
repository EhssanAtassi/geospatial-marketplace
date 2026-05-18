# Civic Data Sources

Where to get civic GIS data per region. Used by `civic-gis:investment-profile`, `civic-gis:cadastral-publish`, and any skill that needs reference layers.

## Global / Free / No Auth

| Source | Coverage | Data | API / Download |
|---|---|---|---|
| **OpenStreetMap** | Global | Roads, POIs, buildings, land use, admin boundaries | Overpass API (https://overpass-api.de) for queries; Geofabrik / HOTOSM for downloads |
| **Natural Earth** | Global | Country/state boundaries, populated places, physical features | https://www.naturalearthdata.com (download) |
| **SRTM / Copernicus DEM** | Global | Elevation 30m / 90m / 10m | https://portal.opentopography.org (free with registration) |
| **World Bank Open Data** | Country-level | Demographics, economic indicators | https://data.worldbank.org/ (REST API) |
| **OECD** | OECD member countries | Detailed economic/demographic | https://stats.oecd.org (REST API) |
| **UN Stats** | Global | Demographics, SDG indicators | https://unstats.un.org |
| **WorldPop** | Global | High-resolution population grids | https://www.worldpop.org (downloads) |
| **GADM** | Global | Administrative boundaries L0-L5 | https://gadm.org (downloads) |
| **HOTOSM** | Disaster-prone & developing regions | Field-mapped OSM extracts | https://export.hotosm.org |

## Country-Specific (Major)

### United States

| Source | Data | Notes |
|---|---|---|
| **US Census Bureau / TIGER** | Boundaries, demographics, ACS | https://www.census.gov/geographies/mapping-files.html — TIGER/Line shapefiles |
| **Census ACS** | Demographics 5-year + 1-year | https://api.census.gov/data |
| **HUD** | Housing | https://hudgis-hud.opendata.arcgis.com/ |
| **EPA EJScreen** | Environmental justice | https://www.epa.gov/ejscreen |
| **USGS** | Geology, hydrology, DEM | https://www.usgs.gov/products/data-and-tools |
| **State + County portals** | Parcels, zoning | Highly variable; aggregators (ATTOM, CoreLogic) normalize but are paid |

### European Union

| Source | Data | Notes |
|---|---|---|
| **INSPIRE Geoportal** | Pan-EU spatial data, harmonized | https://inspire-geoportal.ec.europa.eu — federated discovery |
| **EuroGeographics** | Boundaries, cadastre cross-walks | https://eurogeographics.org |
| **EUROSTAT** | Demographics, NUTS regions | https://ec.europa.eu/eurostat |
| **Copernicus Land Monitoring** | Land use (CORINE), urban atlas | https://land.copernicus.eu |

### MENA region

| Source | Data | Notes |
|---|---|---|
| **OSM** | Often the best available | Particularly for cities; rural coverage variable |
| **HOTOSM / MapSwipe** | Disaster + reconstruction focus | Syria, Yemen, Iraq coverage |
| **UNHCR Operational Portal** | Refugee/IDP camps, displacement | https://data.unhcr.org |
| **National stat offices** | Demographics | Variable digitization (UAE/SA most modern; others partial) |
| **Government open-data portals** | Coverage growing | data.gov.sa (Saudi Arabia), data.gov.ae (UAE), data.bahrain.bh, etc. |
| **Turkey TKGM** | Cadastre (mature) | https://parselsorgu.tkgm.gov.tr |

### Africa

| Source | Data | Notes |
|---|---|---|
| **AfricaGeoPortal** | Pan-African data, ESRI-hosted | https://www.africageoportal.com |
| **Open Africa Innovation** | Demographics, urban | Per-country |
| **HOTOSM** | OSM extracts | Strong coverage in disaster-affected regions |
| **National stat offices** | Highly variable | Varies country by country |

### Latin America

| Source | Data | Notes |
|---|---|---|
| **GeoSUR** | South American regional | http://www.geosur.info |
| **National IDE portals** | Per-country | IDE-Argentina, IDE-Chile, IDE-Brazil (INDE), etc. |
| **IBGE** | Brazil cadastre + demographics | https://www.ibge.gov.br |

## Asia

| Source | Data | Notes |
|---|---|---|
| **OSM** | Highly variable; strong in Japan, Korea, Southeast Asia | |
| **National portals** | Quality varies | Japan GSI, Korea NSDI very mature; many others growing |
| **OpenAerialMap** | High-res aerial | https://openaerialmap.org |

## API Patterns and Practical Tips

### OSM Overpass — get road network in a bbox

```
[out:json];
(way["highway"~"motorway|trunk|primary|secondary"]
   (minLat,minLng,maxLat,maxLng);
);
out geom;
```

### World Bank — population for a country

```
GET https://api.worldbank.org/v2/country/SYR/indicator/SP.POP.TOTL?format=json
```

### US Census ACS — median household income for a tract

```
GET https://api.census.gov/data/2022/acs/acs5?get=B19013_001E&for=tract:*&in=state:06+county:037
```

## Honest Caveats

1. **OSM coverage varies wildly.** Major cities good, rural areas spotty, conflict zones often out-of-date by months/years.
2. **Demographic data lag** — Census data is typically 1-3 years old by publication. ACS 5-year is averaged over 5 years.
3. **Authoritative ≠ accurate.** Government cadastres can be outdated, incomplete, or contested (Palestine, Western Sahara, Crimea, etc.). Always check the `as_of` date on official sources.
4. **License terms vary.** OSM ODbL (attribution + share-alike), Census public-domain, INSPIRE varies by member state, World Bank CC-BY. Always cite.
5. **Privacy regulations differ.** GDPR (EU), CCPA (California), regional data-protection laws constrain what can be published from a "public" dataset. `civic-gis:cadastral-publish` honors privacy filters by default.

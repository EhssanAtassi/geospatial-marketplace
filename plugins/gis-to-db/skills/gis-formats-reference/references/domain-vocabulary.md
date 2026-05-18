# Domain Vocabulary

Mapping of domain-specific terms to the geometry types, CRS expectations, and ingestion patterns common in each industry. Use this to disambiguate user requests ("ingest the parcels", "import the pipeline routes") and recommend sensible defaults.

## Real Estate / Land Development

| Term | Geometry | Typical CRS | Source format | Notes |
|---|---|---|---|---|
| **Parcel** / **lot** | `Polygon` or `MultiPolygon` | Local UTM (e.g. EPSG:32637 for Levant) | Shapefile, `.gdb` | Most common ingestion. Always reproject to 4326 for storage. Attributes typically include `parcel_id`, `area_sqm`, `zone`, `owner`. |
| **Building footprint** | `Polygon` or `MultiPolygon` | Same as parcels | Shapefile, DWG | Often delivered as DWG by architects. Layer name commonly `BUILDINGS` or `FOOTPRINT`. |
| **Site plan** | Mixed: `Polygon` + `LineString` (roads, utilities) + `Point` (entrances) | Local survey or building-relative mm | DWG / DXF | The hardest input — heterogeneous layers, often no CRS. Validator should list layers and ask which to ingest. |
| **Floor plan** | `Polygon` (rooms) + `LineString` (walls) | None (relative coordinates) | DWG | Usually NOT geographic — skip unless project specifically requires georef'd interior maps. |
| **Subdivision boundary** | `Polygon` | Local UTM | Shapefile, `.gdb` | Single outer ring; check for `MULTIPOLYGON` when subdivision has detached areas. |

### Common workflow for real estate

1. User receives `.gdb` from city cadastre or `.dwg` from architect.
2. Use `/gis-to-db:inspect` to see layers and CRS.
3. Validator prompts for layer filter (typically `PARCELS` + `BUILDINGS`) and source CRS.
4. Use `/gis-to-db:convert` for one-off review, or `/gis-to-db:add-module` to wire into an existing real-estate platform.

## Government / Cadastre / Land Registry

| Term | Geometry | Typical CRS | Source format | Notes |
|---|---|---|---|---|
| **Cadastral parcel** | `Polygon` | National grid (e.g. EPSG:31370 Belgian Lambert 72) | `.gdb`, sometimes Shapefile | Highly standardized within a country. Has official attributes: `cadastre_id`, `area_legal`, `owner_id`, `tax_value`. |
| **Administrative boundary** | `MultiPolygon` | National grid or 4326 | Shapefile | Country / state / city / district / neighborhood hierarchies. |
| **Zoning area** | `MultiPolygon` | National grid | Shapefile, `.gdb` | Land-use designations: residential, commercial, industrial, agricultural, protected. |
| **Land registry boundary** | `Polygon` | National grid | `.gdb` | Legal property lines — different from physical parcel boundaries; treat as authoritative. |
| **Street centerline** | `LineString` or `MultiLineString` | National grid | Shapefile | For routing and addressing. |
| **Address point** | `Point` | National grid | Shapefile, CSV | One point per physical address. |

### Common workflow for government

1. Receives bulk `.gdb` from national mapping agency (e.g. Ordnance Survey, IGN, NSDI).
2. Use `/gis-to-db:scaffold-service` to build an ingestion microservice with API key auth and async jobs (files are large, ingestion takes minutes).
3. Schedule re-ingestion as periodic cron — out of scope for v0.1 but a natural v0.2 feature.

## Utilities (Water / Power / Telecom / Gas)

| Term | Geometry | Typical CRS | Source format | Notes |
|---|---|---|---|---|
| **Pipeline route** | `LineString` or `MultiLineString` | Local UTM | Shapefile, DWG | Often delivered as DWG by engineering firms. |
| **Service area** | `Polygon` | Local UTM | Shapefile | Buffered around assets. |
| **Pole** / **tower** | `Point` | National grid | Shapefile, CSV | Sometimes delivered as CSV with lat/lng columns. |
| **Substation** | `Polygon` (small) | Local UTM | Shapefile, DWG | Often a complex polygon with internal structure when DWG. |
| **Manhole** | `Point` | National grid | CSV, Shapefile | Hundreds of thousands per city. |
| **Service connection** | `LineString` (short, last-mile) | Local UTM | Shapefile | Connects pipeline to building. |

### Common workflow for utilities

1. DWG files from engineering firms during design phase.
2. Shapefile / `.gdb` from GIS team during operational phase.
3. Layer filtering is critical — DWGs contain non-geographic annotations (dimensions, labels).
4. CRS is consistently local UTM zone — store in settings as `default_source_crs`.

## Environmental / Conservation

| Term | Geometry | Typical CRS | Source format | Notes |
|---|---|---|---|---|
| **Protected area** | `Polygon` or `MultiPolygon` | 4326 (international) or national grid | Shapefile, KML | World Database on Protected Areas (WDPA) ships in Shapefile/4326. |
| **Flood zone** | `Polygon` or `MultiPolygon` | National grid | Shapefile, `.gdb` | FEMA flood maps in the US, Environment Agency in UK. |
| **Habitat range** | `Polygon` | 4326 | Shapefile, GeoJSON | Often global-scale; many polygons across hemispheres. |
| **Water body** | `Polygon` | National grid or 4326 | Shapefile | Lakes, reservoirs, coastlines. |
| **Watershed** | `Polygon` | National grid | Shapefile, `.gdb` | Hydrologic Unit Code (HUC) in US. |
| **Forest stand** | `Polygon` | National grid | Shapefile | Sometimes attributes encoded as 2-letter codes (species, age class). |

### Common workflow for environmental

1. Public-domain Shapefile downloads from government agencies.
2. Use `/gis-to-db:make-cli` for one-shot CLI to ingest into PostGIS for analysis.
3. Storage tends to be PostGIS for analytics-heavy workflows or MongoDB for web-app overlays.

## Survey / Topographic

| Term | Geometry | Typical CRS | Source format | Notes |
|---|---|---|---|---|
| **Contour line** | `LineString` | Local UTM | Shapefile, DWG | Elevation as attribute. |
| **Spot elevation** | `Point` with Z | Local UTM | Shapefile (3D), DWG | Z coordinate carries elevation in meters or feet. |
| **TIN** (triangulated irregular network) | `Polygon` (triangles) | Local UTM | DWG, Shapefile | Massive feature counts; consider PostGIS `geometry(Polygon Z, 4326)` or skip Z. |
| **Boundary survey** | `Polygon` | Local survey grid | DWG | Hand-drawn vertex precision; respect it (don't simplify). |
| **GPS track** | `LineString` | 4326 | GPX, KML | GPS-recorded, always WGS84. |

### Common workflow for survey

1. Engineering firm delivers DWG.
2. Validator prompts for source CRS (always required for DWG) and layer filter.
3. Often need to preserve Z — use 3D PostGIS or store elevation as a separate attribute.

## Telecom-specific (5G / Fiber)

| Term | Geometry | Typical CRS | Source format | Notes |
|---|---|---|---|---|
| **Cell tower** | `Point` | 4326 or local UTM | CSV, Shapefile | Includes azimuth, tilt as attributes. |
| **Coverage cell** | `Polygon` | 4326 | KML, Shapefile | RF-engineering output; high vertex counts. |
| **Fiber route** | `LineString` | Local UTM | Shapefile, DWG | Often DWG from construction phase. |
| **Splice point** | `Point` | 4326 | CSV, Shapefile | Hundreds of thousands per metro. |

## Disambiguation Rules

When a user uses ambiguous terms, prefer these defaults:

- "**polygon**" alone → assume `MultiPolygon` for ingestion (most data has multi-part features).
- "**boundary**" → `Polygon` (closed ring).
- "**route**" / "**path**" / "**alignment**" → `LineString`.
- "**point**" / "**location**" / "**address**" → `Point`.
- "**area**" → context-dependent: `Polygon` if vector, `Raster` (out of scope) if continuous.

When the domain is unclear and the file is a DWG:

- Layer name `PARCEL*` / `LOT*` / `PROPERTY*` → real-estate parcels.
- Layer name `BUILDING*` / `FOOTPRINT*` / `STRUCTURE*` → building footprints.
- Layer name `ROAD*` / `STREET*` / `CL*` (centerline) → linear infrastructure.
- Layer name `PIPE*` / `WATER*` / `SEWER*` / `GAS*` / `ELEC*` → utility lines.
- Layer name `0` / `DEFPOINTS` / `DIMENSION*` / `TEXT*` / `ANNOTATION*` → skip (non-geographic).

## CRS by region (quick lookup)

| Region | Typical projected CRS for cadastral data |
|---|---|
| Syria / Lebanon / Jordan | EPSG:32636 or 32637 (UTM 36N / 37N) |
| Saudi Arabia / Iraq / Iran | EPSG:32637, 32638, 32639 (UTM 37N–39N) |
| Egypt | EPSG:22992 (Egypt Red Belt) or 32636 (UTM 36N) |
| Turkey | EPSG:32635, 32636, 32637, 32638 (UTM 35N–38N) |
| UK | EPSG:27700 (British National Grid) |
| France | EPSG:2154 (RGF93 / Lambert-93) |
| Germany | EPSG:25832, 25833 (ETRS89 / UTM 32N, 33N) |
| Belgium | EPSG:31370 (Belgian Lambert 72) |
| Netherlands | EPSG:28992 (RD New) |
| US (varies by state) | EPSG:26910-26920 (UTM 10-20N) or State Plane Coordinate System |
| US (national) | EPSG:4269 (NAD83) for geographic, EPSG:5070 (Albers Equal Area Conic) for analysis |
| Canada | EPSG:3347 (Lambert Conformal Conic) |
| Brazil | EPSG:31984-31985 (SIRGAS 2000 / UTM 24S-25S) |
| Australia | EPSG:7855-7858 (GDA2020 / MGA 55-58) |
| Japan | EPSG:6669-6687 (JGD2011 / Plane Rectangular CS I–XIX) |
| China | EPSG:4490 (CGCS2000) — but obscured by GCJ-02 for public use |

Use this table to suggest a default source CRS when the user provides a region but not a code.

# Cadastral Systems Reference

Parcel identification schemes, deed structures, and land-registry data formats across major regions. Reference for civic-gis skills that work with official cadastral data.

## Parcel ID Schemes

| Region | Scheme | Example | Notes |
|---|---|---|---|
| **United States** | APN (Assessor's Parcel Number) — county-specific format | `123-456-789` (Los Angeles County) | Format varies by county. Always county-namespaced. |
| **United States** | PIN (Property Identification Number) | `2204001005000` | Used by Cook County (Chicago) and some others. |
| **UK** | Title Number | `K123456` | Land Registry. One per registered title. |
| **France** | Numéro de Parcelle Cadastrale | `123 AB 45` (commune, section, parcelle) | Three-part hierarchical. |
| **Germany** | Flurstück | `Gemarkung 123, Flur 4, Flurstück 56/2` | Three-part: district / Flur / parcel + slash for split parcels. |
| **Netherlands** | Kadastrale Aanduiding | `STD00 A 1234` (gemeente, sectie, perceel) | BAG/Kadaster system. |
| **Switzerland** | E-GRID | `CH123456789012` | National 14-char identifier. |
| **Syria / Lebanon / Jordan** | تابو (Tapu) — Ottoman-origin | `<مدينة>-<حي>-<قطعة>` | District-based. Pre-conflict Syria used handwritten registers; digitization is patchy post-2011. |
| **Saudi Arabia** | Title Deed Number | issued by Real Estate Registry | National e-registry since 2017. |
| **Turkey** | Tapu Müdürlüğü Sicil No | `<il>-<ilçe>-<ada>-<parsel>` | Province-district-block-parcel. |
| **Egypt** | حوض / قطعة (Hawd / Qit'aa) | `<governorate>-<district>-<hawd>-<qit'aa>` | Land Registry under Ministry of Justice. |
| **Brazil** | CCIR (rural) + IPTU (urban) | varies by municipality | National rural cadastre (INCRA) + municipal urban. |
| **Australia** | Volume/Folio | `12345/678` | State-specific. |
| **Japan** | 不動産番号 (Fudosan Bangō) | 13-digit national | Legal Affairs Bureau. |

### Universal Rule

**Never assume parcel IDs are unique across jurisdictions.** Always carry the jurisdiction alongside:

```json
{"jurisdiction": "homs-syria", "parcel_id": "H-2034-12"}
```

## Deed and Title Structures

### Common fields in a land-registry deed

| Field | Description |
|---|---|
| `deed_number` / `title_number` | Stable across changes of owner |
| `parcel_id` | The cadastral ID |
| `owner_name(s)` | Multiple possible (joint ownership) |
| `owner_share` | Fraction (1/2, 1/4) when joint |
| `area_official` | Authoritative area; may differ from GIS-computed area |
| `boundary_description` | Textual ("metes and bounds") in older systems |
| `easements` | Right of way, utility, etc. |
| `liens / encumbrances` | Mortgages, tax liens, court orders |
| `acquired_date` | When current owner acquired |
| `acquired_via` | Purchase, inheritance, court order, restitution |
| `registered_date` | When this deed was registered |
| `prior_deed_ref` | Reference to predecessor deed |

### Why deeds are NOT the same as GIS parcels

- **One deed can cover multiple parcels** (a property assembled from purchases).
- **One parcel can have multiple deeds in succession** (after sales).
- **Boundary discrepancies** between deed text ("metes and bounds") and the GIS polygon are common, especially in older / handwritten registries.

`civic-gis:cadastral-publish` and `civic-gis:reconstruction-tracker` must keep deed and parcel as distinct concepts.

## Country-Specific Notes

### Syria

- Pre-2011 cadastre held by **Directorate of Cadastral Affairs** (مديرية الشؤون العقارية), under Ministry of Local Administration.
- Most pre-conflict records on paper. Digital coverage was being rolled out 2008-2011 but incomplete.
- Post-2011 challenges: destroyed registries (Homs Governorate building damaged, Aleppo registry partially destroyed), conflicting claims, displaced persons.
- Reconstruction efforts (Decree 66/2012, Law 10/2018) created controversial new urban planning zones; international standards (Pinheiro Principles) call for property restitution that those laws sometimes circumvent.
- For `civic-gis:reconstruction-tracker`: assume baselines are partial, frequently paper-only, and must be reconciled with whatever digital pre-conflict records survived.

### Iraq / Kurdistan

- Iraqi General Directorate of Real Estate Registration. Federal but with Kurdish Regional Government parallel system in KRG areas.
- IS occupation 2014-2017 destroyed registries in Mosul, Tikrit, parts of Anbar. Restoration ongoing.

### Lebanon

- General Directorate of Land Registry and Cadastre under Ministry of Finance.
- 1975-1990 civil war destroyed some records; complete national digital cadastre still incomplete.

### Turkey

- **TKGM** (Tapu ve Kadastro Genel Müdürlüğü) — fully digitized, online lookup, well-structured.
- Good model for reconstruction projects aiming at modern cadastre.

### Jordan

- **Department of Lands and Survey**. Modern digital cadastre with online access.

### Israel / Palestine

- **Israel Land Authority** + Tabu (deeds registry).
- Palestinian Authority operates a parallel registry in Areas A & B; Area C governance contested.
- Highly politicized; civic-gis must explicitly carry jurisdiction info to avoid implicit positions.

### US — practical pitfalls

- County-level ownership of cadastre, so `parcel_id` schemes vary by county within a state.
- Aggregator services (ATTOM, CoreLogic) normalize across counties for fees.
- Public records are state law — some states make owner names public, some don't. `civic-gis:cadastral-publish` privacy filter must be jurisdiction-aware.

## Data Formats

| Source | Format | Notes |
|---|---|---|
| ESRI File Geodatabase (.gdb) | Vector cadastre | Industry standard. Read via `gis-to-db:inspect`. |
| Shapefile (.shp) | Vector | Common interchange. |
| GeoJSON | Vector | Web-friendly. |
| GeoPackage (.gpkg) | Vector | Modern replacement for Shapefile. |
| Land XML | XML | Surveying interchange. |
| **PDF + scanned images** | Image | Reality of many post-conflict cadastres. OCR + georeferencing required. Outside v0.1 scope. |
| **Paper-only / oral records** | — | Genuine challenge in post-conflict zones. Reconstruction-tracker should flag parcels with no digital baseline. |

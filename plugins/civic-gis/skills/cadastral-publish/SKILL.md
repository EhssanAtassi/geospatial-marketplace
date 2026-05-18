---
name: cadastral-publish
description: This skill should be used when the user asks to "publish the cadastre", "generate a public-facing parcel map", "create a parcel lookup API", "produce official extract PDF", "publish land registry to the web", "generate cadastre change log", "public cadastre publication", or invokes `/civic-gis:cadastral-publish`. Takes an official cadastral dataset (typically the output of `gis-to-db:convert` to PostGIS or MongoDB) and produces public-facing artifacts: a searchable Leaflet map, parcel-extract PDF templates, JSON API stubs, and a change log against the previous publication.
argument-hint: --cadastre path/to/cadastre.geojson [--db postgis|mongo] [--output-dir ./public-cadastre] [--language en|ar|fr] [--previous path/to/last-publication.geojson]
allowed-tools: Bash, Read, Write, Glob
---

# Cadastral Publish

> **v0.1 status — SKILL.md only. Composes on top of `gis-to-db:convert` (data → DB) and uses `map-styling:leaflet-cookbook` patterns for the public map. Full orchestrator + Leaflet template land in v0.2.**

Generate public-facing artifacts from an official cadastral dataset. The output is suitable for posting on a municipal website or distributing to citizens.

## When to Use

- `/civic-gis:cadastral-publish --cadastre official-2025-q2.geojson --output-dir ./www/cadastre`
- "Generate a public parcel-lookup map from this cadastre."
- "Create official-extract PDFs for these parcels."
- "Publish the new cadastre version to the web with a change log."

## Output Artifacts

In `--output-dir`:

```
public-cadastre/
├── index.html              # Leaflet map with parcel search, click-to-detail
├── parcels.geojson         # Public-safe copy (sensitive fields stripped)
├── parcels.csv             # Tabular export
├── api/
│   └── parcel/<id>.json    # Pre-rendered per-parcel JSON for static-API serving
├── extracts/
│   └── template.html       # HTML template for official extracts (convertible to PDF)
├── changelog.md            # Diff vs --previous (if provided)
└── README.md               # How to host and update
```

## How It Works

1. Validator agent runs first (`civic-preflight-validator`, mode=cadastral-publish).
2. Read cadastre input (GeoJSON or via DB query through `gis-to-db:convert`).
3. **Strip sensitive fields.** Public-facing copy must NOT include: owner personal info, sale prices, tax assessments, internal references. Configurable in settings.
4. Generate searchable Leaflet map (HTML + JS) with:
   - Parcel polygons (color-coded by zone if zone data present)
   - Click handler → side panel with public-safe attributes
   - Search box: by parcel_id, by address, by owner-name (if owner names are public per jurisdiction)
5. Pre-render per-parcel JSON files for a static-API pattern (one file per parcel, served as `/api/parcel/<id>.json`).
6. Generate HTML extract template (header, parcel summary, geometry preview, attribute table, footer with official seal placeholder).
7. If `--previous` provided, run `gis-to-db:analyze-diff` and render a human-readable changelog.

## Privacy and Sensitivity

The plugin applies a **deny-list** of sensitive field patterns by default:

- `owner_*`, `taxpayer_*`, `purchase_price`, `tax_value`, `valuation_*`
- `phone`, `email`, `id_number`, `national_id`
- `internal_*`, `staff_note*`, `comment`

Configurable in `.claude/civic-gis.local.md`:

```yaml
cadastral_publish:
  sensitive_field_patterns:
    - owner_*
    - tax_value
  public_owner_names: false   # set true only where owner names are legally public records
```

## v0.2 Plans

- Pre-built Leaflet template with multilingual support.
- PDF generation via pandoc / Chromium-headless.
- ArcGIS Online and CartoDB connector for orgs using hosted GIS.
- WFS/WMS endpoint generation for inter-agency data sharing.

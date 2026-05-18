---
name: gis-formats-reference
description: This skill should be used when the user mentions GIS or CAD file formats ("Shapefile", "GeoJSON", ".gdb", "File Geodatabase", "DWG", "DXF", "KML"), geospatial actions ("convert GIS file", "import shapefile", "ingest geometry", "load spatial data"), CRS or projection topics ("EPSG", "SRID", "WGS84", "reproject", "UTM zone", "coordinate system"), DB-specific spatial features ("PostGIS", "ST_GeomFromGeoJSON", "geometry vs geography", "2dsphere index", "MongoDB GeoJSON", "MySQL spatial", "GIST index"), GDAL tooling ("fiona", "geopandas", "ogr2ogr", "ezdxf", "LibreDWG"), or domain-specific geometry work ("parcel boundaries", "cadastral data", "site plan", "building footprint", "zoning", "pipeline route", "flood zone", "topographic", "land registry").
---

# GIS / CAD Formats and Spatial Database Reference

This skill provides reference knowledge for working with GIS and CAD file formats, coordinate reference systems (CRS), and the spatial features of PostGIS, MongoDB, and MySQL. It activates silently to inform answers about geospatial file handling, projection issues, and database-specific geometry storage — without requiring the user to invoke a command.

## When This Skill Helps

Use this skill's content when answering questions that involve:

- Reading or describing the structure of a Shapefile, ESRI File Geodatabase (`.gdb`), DWG, DXF, GeoJSON, or KML/KMZ file.
- Choosing between WGS84 (EPSG:4326) and a local projected CRS (UTM zones, country-specific systems).
- Picking between `geometry` and `geography` in PostGIS, or between GeoJSON-in-document vs separate-collection layouts in MongoDB.
- Writing PostGIS `ST_*` queries, MongoDB `$geoWithin` / `$near` / `$geoIntersects` queries, or MySQL 8 spatial queries.
- Diagnosing CRS axis-order surprises (e.g., MongoDB requires `[lng, lat]`, some PostGIS contexts use `[lat, lng]`).
- Reading or transforming DWG/DXF layers into Shapely geometries via the LibreDWG + ezdxf pipeline.

## Key Reference Files

For detailed content, see:

- `references/formats.md` — Shapefile / .gdb / DWG / DXF / GeoJSON / KML internals, header inspection commands, expected files and quirks per format.
- `references/crs-srid.md` — EPSG code guide, WGS84 vs local projections, axis-order traps, pyproj usage, reprojection commands.
- `references/postgis.md` — geometry vs geography, GIST indexes, ST_* cheatsheet, common patterns, performance pitfalls.
- `references/mongodb.md` — GeoJSON in documents, 2dsphere indexes, $geoWithin / $near / $geoIntersects, coordinate format rules.
- `references/mysql-spatial.md` — MySQL 8 spatial types, SRID handling, ST_* differences from PostGIS, R-tree indexes.
- `references/gdal-toolbox.md` — osgeo/gdal Docker image, ogr2ogr / fiona / geopandas / ezdxf / LibreDWG cheatsheet.
- `references/domain-vocabulary.md` — Real-estate, cadastral, government, utility, environmental, survey vocabulary mapped to common geometry types and CRS expectations.

## Core Rules

Apply these rules without needing to load a reference file:

1. **MongoDB GeoJSON coordinate order is `[longitude, latitude]`** — never `[lat, lng]`. This is the most common bug.
2. **PostGIS `geometry` is planar, `geography` is geodesic.** Use `geometry(Polygon, 4326)` for storage + GIST indexing in most cases; switch to `geography` only when geodesic distance correctness matters more than performance.
3. **Always reproject to a common SRID before ingesting.** Mixed-SRID tables break spatial joins silently. EPSG:4326 (WGS84) is the safe default unless the user has a specific reason for a projected CRS.
4. **ESRI `.gdb` is a directory, not a file.** Tools must point to the `.gdb/` folder, not to an individual file inside it.
5. **DWG drawings usually lack CRS metadata.** Always require the user to supply the source CRS for DWG/DXF inputs.
6. **Run `ogr2ogr` or `fiona` from inside the `osgeo/gdal` Docker image** when the host system lacks GDAL. Default image: `osgeo/gdal:ubuntu-small-3.8.0`.

## Additional Resources

Skill contents are organized for progressive disclosure. Read the reference file relevant to the user's question; SKILL.md should remain the entry point for triggering and high-level rules.

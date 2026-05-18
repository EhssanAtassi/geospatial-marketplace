# Example: Shapefile → PostGIS

End-to-end example showing the full input → command → output flow for a real cadastral Shapefile ingested into PostGIS.

## Input

```
/data/damascus-parcels/damascus.shp
/data/damascus-parcels/damascus.shx
/data/damascus-parcels/damascus.dbf
/data/damascus-parcels/damascus.prj   # contains EPSG:32637 WGS_1984_UTM_Zone_37N
/data/damascus-parcels/damascus.cpg   # UTF-8
```

**Inspection summary** (from `/gis-to-db:inspect`):

- Format: Shapefile
- Driver: ESRI Shapefile
- Geometry: `Polygon` (1,247 features)
- CRS: `EPSG:32637` (UTM Zone 37N, eastings/northings in meters)
- Bounds: (252413.789, 3704512.346) → (276891.234, 3722098.876)
- Attributes:
  - `parcel_id` (str:32)
  - `area_sqm` (float)
  - `zone` (str:16)
  - `owner` (str:128)

## Command

```bash
python gis_convert.py /data/damascus-parcels/damascus.shp \
  --target postgis \
  --table-name damascus_parcels \
  --ddl \
  --target-srid 4326 \
  --limit 5
```

(`--limit 5` keeps the chat output short; the full file lands in `/tmp/damascus_parcels.sql` with all 1,247 features.)

## Output (chat-truncated)

```sql
-- Source: /data/damascus-parcels/damascus.shp
-- Format: Shapefile
-- Target: postgis (SRID 4326)
-- Full output saved to: /tmp/damascus_parcels.sql
-- Features emitted: 1247 (chat truncated to 5)

-- PostGIS DDL for damascus_parcels
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS damascus_parcels (
  id BIGSERIAL PRIMARY KEY,
  parcel_id TEXT,
  area_sqm DOUBLE PRECISION,
  zone TEXT,
  owner TEXT,
  geom geometry(Geometry, 4326) NOT NULL
  ,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS damascus_parcels_geom_gist ON damascus_parcels USING GIST (geom);

INSERT INTO damascus_parcels (parcel_id, area_sqm, zone, owner, geom) VALUES ('DM-001-247', 1947.5, 'residential', 'Ministry of Awqaf', ST_GeomFromGeoJSON('{"type":"Polygon","coordinates":[[[36.30134,33.51247],[36.30178,33.51247],[36.30178,33.51289],[36.30134,33.51289],[36.30134,33.51247]]]}'));
INSERT INTO damascus_parcels (parcel_id, area_sqm, zone, owner, geom) VALUES ('DM-001-248', 2103.8, 'residential', 'Private', ST_GeomFromGeoJSON('{"type":"Polygon","coordinates":[[[36.30178,33.51247],[36.30224,33.51247],[36.30224,33.51289],[36.30178,33.51289],[36.30178,33.51247]]]}'));
INSERT INTO damascus_parcels (parcel_id, area_sqm, zone, owner, geom) VALUES ('DM-001-249', 894.2, 'commercial', 'Municipality of Damascus', ST_GeomFromGeoJSON('{"type":"Polygon","coordinates":[[[36.30224,33.51247],[36.30248,33.51247],[36.30248,33.51268],[36.30224,33.51268],[36.30224,33.51247]]]}'));
INSERT INTO damascus_parcels (parcel_id, area_sqm, zone, owner, geom) VALUES ('DM-001-250', 1547.3, 'residential', 'Private', ST_GeomFromGeoJSON('{"type":"Polygon","coordinates":[[[36.30248,33.51247],[36.30289,33.51247],[36.30289,33.51289],[36.30248,33.51289],[36.30248,33.51247]]]}'));
INSERT INTO damascus_parcels (parcel_id, area_sqm, zone, owner, geom) VALUES ('DM-001-251', 1247.6, 'residential', 'Private', ST_GeomFromGeoJSON('{"type":"Polygon","coordinates":[[[36.30289,33.51247],[36.30324,33.51247],[36.30324,33.51289],[36.30289,33.51289],[36.30289,33.51247]]]}'));
-- ⚠ Output truncated to 5 features for chat readability. Full output saved to /tmp/damascus_parcels.sql.

-- Run with: psql <connection-string> -f /tmp/damascus_parcels.sql
```

## What happened under the hood

1. **CRS detection**: `fiona.open(...).crs` returned the CRS dict derived from the `.prj` (EPSG:32637).
2. **Reprojection**: each feature's geometry was reprojected from UTM Zone 37N → EPSG:4326 via `pyproj.Transformer(..., always_xy=True)`. Coordinate order ended up `[lng, lat]` — e.g. parcel DM-001-247 became `[36.30134, 33.51247]` (longitude, latitude) — Damascus city center.
3. **Schema introspection** (for DDL): `src.schema["properties"]` gave the attribute name/type pairs, which were mapped to PostgreSQL types (`str:32` → `TEXT`, `float` → `DOUBLE PRECISION`).
4. **GeoJSON serialization**: each Shapely geometry was converted via `shapely.geometry.mapping()` and serialized with `json.dumps()` (compact, single-line) and wrapped in `ST_GeomFromGeoJSON(...)`.
5. **Truncation**: features 1-5 went to both stdout and `/tmp/damascus_parcels.sql`; features 6-1247 went only to the file.

## Running the output

```bash
# Local PostgreSQL
psql "postgresql://postgres:secret@localhost:5432/realestate" -f /tmp/damascus_parcels.sql

# Verify
psql "postgresql://postgres:secret@localhost:5432/realestate" \
  -c "SELECT COUNT(*) FROM damascus_parcels;"
#  count
# -------
#  1247
```

## Variants

### Without `--ddl`

Omitting `--ddl` skips the `CREATE TABLE` and `CREATE INDEX` lines — useful when the table already exists or when you want to append to an existing table.

```bash
python gis_convert.py /data/damascus.shp --target postgis --table-name damascus_parcels
```

Output starts directly with the first `INSERT`.

### Different target SRID

If you specifically want UTM 37N storage (faster planar queries within Syria):

```bash
python gis_convert.py /data/damascus.shp \
  --target postgis \
  --table-name damascus_parcels \
  --target-srid 32637 \
  --ddl
```

In this case **no reprojection happens** (source CRS == target SRID). The DDL emits `geometry(Geometry, 32637)` and inserts wrap `ST_GeomFromGeoJSON(...)` — but the GeoJSON coordinates are still UTM meters, not lat/lng. PostGIS handles this correctly.

### Overriding a missing/wrong source CRS

For a Shapefile missing its `.prj`, or one with a `.prj` that is known to be wrong:

```bash
python gis_convert.py /data/damascus.shp \
  --target postgis \
  --table-name damascus_parcels \
  --source-crs EPSG:32637 \
  --ddl
```

The `--source-crs` flag overrides whatever fiona reads from the file.

## Common errors

### "ERROR 4: Failed to read projection info"

The `.prj` file is missing. Use `--source-crs EPSG:N` to override.

### After loading, points appear in the Indian Ocean

Axis order is swapped. Check:
- For PostGIS, the GeoJSON coordinates should be `[lng, lat]`.
- If the source data appears to be `[lat, lng]`, the source CRS is misidentified — likely a Shapefile with a malformed `.prj` claiming WGS84 but using `[lat, lng]` order in the geometry. Re-run with `--source-crs <real_crs>`.

### "ST_GeomFromGeoJSON: ...mixed-dim coordinates"

The Shapefile contains 3D geometry (X, Y, Z) but the column expects 2D. Workaround: edit the SQL output and wrap each `ST_GeomFromGeoJSON(...)` with `ST_Force2D(...)`. Or pre-strip Z via fiona before re-running. v0.2 should add a `--force-2d` flag.

### Massive output files

For a Shapefile with 100k+ features, the chat output is truncated to `--limit` features but the full `/tmp/<table>.sql` can be hundreds of MB. Consider:

- Use `/gis-to-db:scaffold-service` instead for production ingestion of large files.
- Or generate the SQL and pipe directly into `psql` without staging the file: `python gis_convert.py ... | psql ...` (but the truncation logic still applies — use `--limit 0` to disable, which is a v0.2 feature).

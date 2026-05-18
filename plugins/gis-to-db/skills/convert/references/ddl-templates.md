# DDL Templates

Canonical CREATE TABLE / CREATE INDEX templates used by `gis_convert.py` when `--ddl` is set. These templates favor permissive, polymorphic geometry types so the same DDL works across mixed-geometry inputs.

## PostGIS

### Default (polymorphic geometry)

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS <table> (
  id          BIGSERIAL PRIMARY KEY,
  <col1>      <type1>,
  <col2>      <type2>,
  ...
  geom        geometry(Geometry, <srid>) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS <table>_geom_gist ON <table> USING GIST (geom);
```

### Production-grade variant (homogeneous polygons)

When the input is known to be all Polygon / MultiPolygon, harden the schema:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS <table> (
  id          BIGSERIAL PRIMARY KEY,
  <attrs>     ...,
  geom        geometry(MultiPolygon, 4326) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS <table>_geom_gist ON <table> USING GIST (geom);

-- Defense-in-depth: validate every inserted geometry.
ALTER TABLE <table>
  ADD CONSTRAINT <table>_geom_valid_chk CHECK (ST_IsValid(geom));

ALTER TABLE <table>
  ADD CONSTRAINT <table>_geom_srid_chk CHECK (ST_SRID(geom) = 4326);
```

The validity constraint slows inserts ~5–10% but prevents downstream `ST_Intersects` from misbehaving. Recommended for production tables.

### Production-grade variant (Point data)

```sql
CREATE TABLE IF NOT EXISTS <table> (
  id          BIGSERIAL PRIMARY KEY,
  <attrs>     ...,
  geom        geometry(Point, 4326) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS <table>_geom_gist ON <table> USING GIST (geom);

-- Often useful for points: a separate index on (lng, lat) for fast bounding-box queries
CREATE INDEX IF NOT EXISTS <table>_lng_lat_idx
  ON <table> (ST_X(geom), ST_Y(geom));
```

### Geography column variant (geodesic distance queries)

```sql
CREATE TABLE IF NOT EXISTS <table> (
  id          BIGSERIAL PRIMARY KEY,
  <attrs>     ...,
  geog        geography(Point, 4326) NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS <table>_geog_gist ON <table> USING GIST (geog);
```

Use `geography` only when geodesic distances matter (e.g. nearest-neighbour across continents). 5–10× slower than `geometry` for most workloads.

## MySQL 8 spatial

### Default (polymorphic geometry)

```sql
CREATE TABLE IF NOT EXISTS <table> (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  <col1>      <type1>,
  ...
  geom        GEOMETRY NOT NULL SRID <srid>,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE SPATIAL INDEX <table>_geom_idx ON <table> (geom);
```

### Polygon-specific variant

```sql
CREATE TABLE IF NOT EXISTS <table> (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  <attrs>     ...,
  geom        POLYGON NOT NULL SRID 4326,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE SPATIAL INDEX <table>_geom_idx ON <table> (geom);
```

Note: MySQL POLYGON column won't accept MultiPolygon values. Use `MULTIPOLYGON` if features may be multi-part.

### Critical: SRID is mandatory for R-tree indexes

```sql
-- THIS WILL FAIL at index creation time:
ALTER TABLE <table> ADD COLUMN geom GEOMETRY NOT NULL;  -- no SRID
-- ERROR: "All parts to a SPATIAL index must be NOT NULL." or
-- "InnoDB does not support SRID 0"

-- THIS WORKS:
ALTER TABLE <table> ADD COLUMN geom GEOMETRY NOT NULL SRID 4326;
```

## MongoDB

### Index only (collections are implicit)

```javascript
db.<collection>.createIndex({ "geometry": "2dsphere" });
```

### Compound index (geo + filter)

When most queries filter on a non-geo field first (e.g. `zone`), a compound index speeds them up substantially:

```javascript
db.<collection>.createIndex({ "zone": 1, "geometry": "2dsphere" });
```

The non-geo field should come **before** the geo field in the index key — MongoDB uses the prefix for filtering, then evaluates geo.

### Validation rules (optional)

```javascript
db.runCommand({
  collMod: "<collection>",
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["<key_attr>", "geometry"],
      properties: {
        <key_attr>: { bsonType: "string" },
        geometry: {
          bsonType: "object",
          required: ["type", "coordinates"],
          properties: {
            type: { enum: ["Point", "LineString", "Polygon", "MultiPolygon"] },
            coordinates: { bsonType: "array" }
          }
        }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});
```

The `gis_convert.py` script does NOT emit validation rules by default — they're a v0.2 candidate. Add manually as needed.

## Naming conventions used

| Element | Convention |
|---|---|
| Table / collection name | User-provided via `--table-name`. No transformation. |
| Geometry column | `geom` (SQL), `geometry` (MongoDB). Not configurable in v0.1. |
| GIST index | `<table>_geom_gist` (PostGIS), `<table>_geom_idx` (MySQL). |
| 2dsphere index | Auto-named by MongoDB as `geometry_2dsphere`. |
| Primary key | `id BIGSERIAL` (PostGIS) / `id BIGINT UNSIGNED AUTO_INCREMENT` (MySQL). MongoDB uses `_id`. |
| Timestamp | `created_at` (universally). |

## Why polymorphic geometry by default?

Real-world GIS data often arrives with mixed geometry types in the same dataset:

- A Shapefile of "parcels" sometimes contains stray Point features for survey markers.
- A `.gdb` feature class can mix `Polygon` and `MultiPolygon` features depending on whether each parcel is single-part or multi-part.
- DWG/DXF layers commonly mix LineString and Polygon (closed vs open polylines).

Using `geometry(Geometry, <srid>)` accepts everything and lets the user tighten the schema after manually verifying the data is homogeneous. This avoids "PROMOTE_TO_MULTI" gymnastics during ingestion.

For production tables, switch to a specific type once the data shape is confirmed:

```sql
ALTER TABLE <table>
  ALTER COLUMN geom TYPE geometry(MultiPolygon, 4326)
  USING ST_Multi(geom)::geometry(MultiPolygon, 4326);
```

## Cross-target equivalence

The same dataset stored under each target should yield equivalent query results for common operations:

| Operation | PostGIS | MySQL 8 | MongoDB |
|---|---|---|---|
| Find within bbox | `WHERE geom && ST_MakeEnvelope(...)` | `WHERE MBRContains(envelope, geom)` | `{geometry: {$geoWithin: {$geometry: envelope}}}` |
| Find within 500m | `WHERE ST_DWithin(geom::geography, point::geography, 500)` | `WHERE ST_DistanceSphere(geom, point) < 500` (no index!) | `{geometry: {$near: {$geometry: point, $maxDistance: 500}}}` |
| Spatial join | `JOIN ... ON ST_Intersects(a.geom, b.geom)` | `JOIN ... ON ST_Intersects(a.geom, b.geom)` (slow) | `$lookup` + per-doc `$geoIntersects` (slow) |
| Area in sqm | `ST_Area(geom::geography)` | Reproject + `ST_Area` (no native geodesic) | (not built-in — application code) |

PostGIS is the most feature-complete; MongoDB is the most ergonomic for read-heavy web workloads; MySQL is the most constrained but adequate for ingestion + basic queries.

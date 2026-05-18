# PostGIS Reference

PostGIS adds spatial types and functions to PostgreSQL. The two main types — `geometry` and `geography` — behave differently. Choosing correctly matters for performance and accuracy.

## geometry vs geography

| | `geometry` | `geography` |
|---|---|---|
| Math | Planar (Euclidean) | Geodesic (on the WGS84 ellipsoid) |
| Units | The units of the SRID (degrees for 4326, meters for UTM) | Meters always |
| Speed | Fast | 5–10× slower for distance/area |
| Functions | Hundreds of `ST_*` | Subset of `ST_*` (no `ST_Buffer` for non-4326, no `ST_Centroid` on 4326 geography for points, etc.) |
| Indexable | GIST on bounding box | GIST on great-circle bounding cap |
| Best for | Storage + spatial joins where SRID is projected, or where distances are computed via reprojection | Distance queries near poles / spanning continents |

### Decision rule

- Default: **`geometry(<Type>, 4326)`**. Store as WGS84, use a GIST index, compute distances via `ST_DistanceSphere` (cheap geodesic approximation) or `geography::ST_Distance` (cast on demand).
- Switch to `geography` only when distance accuracy at large scale matters more than query latency.
- Switch to projected `geometry(<Type>, <local_utm_srid>)` only when the dataset is constrained to a single UTM zone and most queries are local distance/area computations.

## Schema template

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE parcels (
  id           BIGSERIAL PRIMARY KEY,
  parcel_id    TEXT UNIQUE NOT NULL,
  area_sqm     DOUBLE PRECISION,
  zone         TEXT,
  geom         geometry(MultiPolygon, 4326) NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- GIST index on the geometry column — always.
CREATE INDEX parcels_geom_gist ON parcels USING GIST (geom);

-- SRID guard — prevents accidental mixed-SRID rows.
ALTER TABLE parcels
  ADD CONSTRAINT parcels_geom_srid_chk
  CHECK (ST_SRID(geom) = 4326);

-- Geometry-type guard (PostGIS enforces this via the column type already,
-- but a CHECK is defensive against migrations that drop the type).
ALTER TABLE parcels
  ADD CONSTRAINT parcels_geom_type_chk
  CHECK (GeometryType(geom) IN ('POLYGON', 'MULTIPOLYGON'));
```

## Inserting from GeoJSON

```sql
INSERT INTO parcels (parcel_id, area_sqm, zone, geom)
VALUES (
  'P-001',
  1247.5,
  'residential',
  ST_GeomFromGeoJSON('{"type":"Polygon","coordinates":[[[37.1,34.8],[37.2,34.8],[37.2,34.9],[37.1,34.9],[37.1,34.8]]]}')
);
```

When the geometry's coordinates are not in 4326, wrap with `ST_Transform`:

```sql
INSERT INTO parcels (parcel_id, geom)
VALUES (
  'P-001',
  ST_Transform(
    ST_SetSRID(ST_GeomFromGeoJSON('...'), 32637),  -- source CRS
    4326                                            -- target CRS
  )
);
```

## Bulk insert from a file via psql

```bash
# Use ogr2ogr to write directly to PostGIS — fastest path for big imports
ogr2ogr \
  -f "PostgreSQL" \
  PG:"host=localhost user=postgres dbname=mydb password=secret" \
  parcels.shp \
  -nln parcels \
  -lco GEOMETRY_NAME=geom \
  -lco FID=id \
  -lco PRECISION=NO \
  -t_srs EPSG:4326 \
  -nlt PROMOTE_TO_MULTI
```

`-nlt PROMOTE_TO_MULTI` is essential when a Shapefile contains `Polygon` features that the target column requires as `MultiPolygon`.

## ST_* cheatsheet

### Reading & inspection

```sql
ST_AsGeoJSON(geom)               -- to GeoJSON string
ST_AsText(geom)                  -- to WKT string
ST_AsBinary(geom)                -- to WKB bytes
ST_SRID(geom)                    -- 4326
GeometryType(geom)               -- 'POLYGON', 'MULTIPOLYGON'
ST_NPoints(geom)                 -- vertex count
ST_Dimension(geom)               -- 0=point, 1=line, 2=polygon
ST_IsValid(geom)                 -- TRUE / FALSE
ST_IsValidReason(geom)           -- explains why invalid
ST_NumGeometries(geom)           -- for Multi*
```

### Measurements

```sql
ST_Area(geom)                    -- area in SRID units (sq degrees for 4326!)
ST_Area(geom::geography)         -- area in square meters
ST_Length(geom)                  -- length in SRID units
ST_Length(geom::geography)       -- length in meters
ST_Perimeter(geom)               -- perimeter in SRID units
ST_DistanceSphere(g1, g2)        -- great-circle distance in meters (cheap)
ST_Distance(g1::geography, g2::geography)  -- geodesic distance in meters (accurate)
```

### Predicates (spatial join workhorses)

```sql
ST_Intersects(a, b)              -- any intersection (boundary or interior)
ST_Contains(a, b)                -- a fully contains b
ST_Within(a, b)                  -- a is fully inside b
ST_Crosses(a, b)                 -- crossing (line crossing polygon, etc.)
ST_Touches(a, b)                 -- share boundary, no interior overlap
ST_Equals(a, b)                  -- geometrically identical
ST_DWithin(a, b, dist)           -- within distance — index-accelerated
ST_DWithin(a::geography, b::geography, dist_meters)  -- in meters
```

### Constructors

```sql
ST_MakePoint(lng, lat)           -- 2D point in unknown SRID
ST_SetSRID(geom, 4326)           -- assign SRID without reprojecting
ST_Transform(geom, 4326)         -- reproject (requires PROJ data)
ST_Buffer(geom, dist)            -- buffer in SRID units
ST_Buffer(geom::geography, dist_meters)::geometry  -- buffer in meters
ST_Centroid(geom)                -- geometric center
ST_ConvexHull(geom_agg)          -- smallest convex polygon containing all
ST_Union(geom_agg)               -- dissolve overlapping geometries
```

### Indexes and performance

```sql
-- Standard GIST index — always create this.
CREATE INDEX <name>_geom_gist ON <table> USING GIST (geom);

-- SP-GIST (alternative for some workloads):
CREATE INDEX <name>_geom_spgist ON <table> USING SPGIST (geom);

-- For very large tables, consider BRIN for purely-ordered data:
-- (rare; only useful when geometry is loosely clustered by row order)
CREATE INDEX <name>_geom_brin ON <table> USING BRIN (geom);
```

Use `EXPLAIN ANALYZE` to verify index usage. If a query scans sequentially, check:

- The WHERE clause uses an indexable predicate (`ST_Intersects`, `ST_DWithin`, `&&` bounding-box operator).
- The geometry SRIDs match on both sides.
- The geometry column is `NOT NULL`.

## Common query patterns

### Find features within a bounding box

```sql
SELECT id, parcel_id
FROM parcels
WHERE geom && ST_MakeEnvelope(37.0, 34.5, 37.5, 35.0, 4326);
```

`&&` is the bounding-box operator — fastest filter, uses the GIST index directly. Follow up with `ST_Intersects` for exact filtering if needed.

### Find features within N meters of a point

```sql
SELECT id, parcel_id, ST_DistanceSphere(geom, ST_MakePoint(37.1, 34.8)) AS dist_m
FROM parcels
WHERE ST_DWithin(geom::geography, ST_MakePoint(37.1, 34.8)::geography, 500)
ORDER BY dist_m
LIMIT 10;
```

`ST_DWithin` with `geography` uses meters directly. Cast to geography only on the WHERE side to enable the GIST index; computed distance can stay as `ST_DistanceSphere`.

### Spatial join

```sql
SELECT p.parcel_id, b.building_id
FROM parcels p
JOIN buildings b ON ST_Intersects(p.geom, b.geom);
```

For performance, ensure both `parcels.geom` and `buildings.geom` have GIST indexes and matching SRIDs.

### Aggregate polygons (dissolve)

```sql
SELECT zone, ST_Union(geom) AS dissolved_geom
FROM parcels
GROUP BY zone;
```

`ST_Union` is expensive — for many rows, use `ST_Collect` (groups without dissolving) or batch the union.

## TypeORM / SQLAlchemy integration

### TypeORM (NestJS)

```typescript
import { Entity, PrimaryGeneratedColumn, Column, Index } from 'typeorm';
import { MultiPolygon } from 'geojson';

@Entity('parcels')
export class Parcel {
  @PrimaryGeneratedColumn('increment')
  id: number;

  @Column({ unique: true })
  parcelId: string;

  @Index({ spatial: true })
  @Column({
    type: 'geometry',
    spatialFeatureType: 'MultiPolygon',
    srid: 4326,
  })
  geom: MultiPolygon;
}
```

### SQLAlchemy + GeoAlchemy2 (FastAPI)

```python
from sqlalchemy import Column, BigInteger, String
from sqlalchemy.ext.declarative import declarative_base
from geoalchemy2 import Geometry

Base = declarative_base()

class Parcel(Base):
    __tablename__ = "parcels"
    id = Column(BigInteger, primary_key=True)
    parcel_id = Column(String, unique=True, nullable=False)
    geom = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=False)
```

## Common errors

| Error | Cause | Fix |
|---|---|---|
| `Operation on mixed SRID geometries` | Two geometries with different SRIDs in same operation | Reproject one: `ST_Transform(g, 4326)` |
| `Geometry has Z dimension but is not LINESTRING/POINT` | 3D geometry where 2D expected | `ST_Force2D(geom)` before insert |
| `function st_geomfromgeojson(text) does not exist` | PostGIS extension not loaded | `CREATE EXTENSION postgis;` |
| `geometry contains non-closed rings` | First and last point of polygon ring differ | `ST_MakeValid(geom)` or fix at source |
| `relation "geometry_columns" does not exist` | PostGIS metadata views missing | Reinstall PostGIS — `DROP EXTENSION postgis CASCADE; CREATE EXTENSION postgis;` |

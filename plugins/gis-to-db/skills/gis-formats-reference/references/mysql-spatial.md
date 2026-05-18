# MySQL 8 Spatial Reference

MySQL 8 has solid OGC-compliant spatial support. Less featureful than PostGIS but adequate for most ingestion-and-query workflows. Differences from PostGIS are noted throughout.

## Spatial types

| Type | Notes |
|---|---|
| `POINT` | Single 2D coordinate. |
| `LINESTRING` | Connected line segments. |
| `POLYGON` | Closed ring(s); first ring is outer, subsequent rings are holes. |
| `MULTIPOINT` / `MULTILINESTRING` / `MULTIPOLYGON` | Collections of the above. |
| `GEOMETRY` | Polymorphic — holds any of the above. Use sparingly; explicit types are preferred. |
| `GEOMETRYCOLLECTION` | Mixed; rarely needed. |

There is **no `geography` type** in MySQL — all computations are planar within the column's SRID. Use SRID 4326 for storage; expect distance functions to return meters via `ST_Distance` only if both geometries are in a geographic SRID.

## Column definition with SRID

```sql
CREATE TABLE parcels (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  parcel_id   VARCHAR(64) UNIQUE NOT NULL,
  area_sqm    DOUBLE,
  zone        VARCHAR(64),
  geom        POLYGON NOT NULL SRID 4326,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- R-tree spatial index — MySQL's only spatial index type.
-- Requires the geometry column to be NOT NULL and SRID-constrained.
CREATE SPATIAL INDEX parcels_geom_idx ON parcels (geom);
```

**SRID 0 vs 4326**:

- `SRID 0` = no SRID. Distances are unitless, in Cartesian space. Suitable only for game maps or local coordinate puzzles.
- `SRID 4326` = WGS84. Distances are meters when both inputs are 4326. **Use this for real geographic data.**

Once a column is declared `SRID 4326`, MySQL rejects inserts of mismatched-SRID geometries. This is a strict guarantee — and a frequent source of `Cannot get geometry object from data you send to the GEOMETRY field` errors. Always wrap GeoJSON inserts with `ST_GeomFromGeoJSON(..., <options>, 4326)`.

## Insert from GeoJSON

```sql
INSERT INTO parcels (parcel_id, area_sqm, zone, geom)
VALUES (
  'P-001',
  1247.5,
  'residential',
  ST_GeomFromGeoJSON(
    '{"type":"Polygon","coordinates":[[[37.1,34.8],[37.2,34.8],[37.2,34.9],[37.1,34.9],[37.1,34.8]]]}',
    2,            -- option: 2 = accept higher-dim coordinates, drop Z/M
    4326          -- SRID
  )
);
```

Second argument to `ST_GeomFromGeoJSON`:

- `1` (default) — reject any GeoJSON containing 3D / 4D coordinates.
- `2` — accept higher-dim coordinates, strip Z and M.
- `4` — accept and keep Z (rarely useful in MySQL — most functions are 2D-only).

Always pass `2` when ingesting from sources that may include Z (DWG/DXF in particular).

## Insert from WKT (alternative)

```sql
INSERT INTO parcels (parcel_id, geom)
VALUES (
  'P-001',
  ST_GeomFromText(
    'POLYGON((37.1 34.8, 37.2 34.8, 37.2 34.9, 37.1 34.9, 37.1 34.8))',
    4326
  )
);
```

WKT is sometimes more compact than GeoJSON for simple polygons.

## ST_* function reference

### Inspection

```sql
ST_AsGeoJSON(geom)           -- to GeoJSON
ST_AsText(geom)              -- to WKT
ST_AsBinary(geom)            -- to WKB
ST_SRID(geom)                -- 4326
ST_GeometryType(geom)        -- 'Polygon', 'MultiPolygon', etc.
ST_NumPoints(geom)           -- vertex count
ST_IsSimple(geom)            -- TRUE if not self-intersecting
ST_IsValid(geom)             -- TRUE if topologically valid (MySQL 8.0.18+)
```

### Measurements

```sql
ST_Area(geom)                -- planar area in SRID units
ST_Length(geom)              -- planar length
ST_Distance(g1, g2)          -- in meters when both are 4326
ST_DistanceSphere(g1, g2)    -- great-circle distance in meters (works for 4326)
```

For accurate areas of large polygons in 4326, MySQL has **no built-in geodesic area function** — you must reproject to a local projected CRS (e.g. UTM) and use `ST_Area` there. This is a real limitation vs PostGIS.

### Predicates

```sql
ST_Intersects(a, b)
ST_Contains(a, b)
ST_Within(a, b)
ST_Touches(a, b)
ST_Equals(a, b)
MBRIntersects(a, b)          -- bounding-box-only — faster, index-friendly
MBRContains(a, b)
MBRWithin(a, b)
```

### Constructors

```sql
ST_PointFromText('POINT(37.1 34.8)', 4326)
ST_SetSRID(...)              -- NOT available in MySQL; use the second arg of constructors
ST_Transform(geom, target_srid)   -- MySQL 8.0.18+, requires PROJ data installed
ST_Buffer(geom, dist)        -- in SRID units; for 4326, dist is in degrees (not useful directly)
ST_Centroid(geom)
```

## Reprojection

```sql
-- Reproject UTM Zone 37N to WGS84
SELECT ST_AsGeoJSON(ST_Transform(geom, 4326))
FROM parcels_utm37
WHERE id = 1;
```

`ST_Transform` requires the MySQL server to have the PROJ library and grid files. On Docker images, install with:

```dockerfile
RUN apt-get update && apt-get install -y libproj-dev proj-data proj-bin
```

If `ST_Transform` fails with "Unknown EPSG code", reproject **before** inserting using Python (pyproj) — much more reliable.

## Query patterns

### Find within a bounding box

```sql
SELECT id, parcel_id
FROM parcels
WHERE MBRContains(
  ST_GeomFromText('POLYGON((37.0 34.5, 37.5 34.5, 37.5 35.0, 37.0 35.0, 37.0 34.5))', 4326),
  geom
);
```

`MBR*` (Minimum Bounding Rectangle) predicates compare bounding boxes only — orders of magnitude faster than `ST_Intersects` and index-friendly.

### Find within N meters

```sql
SELECT id, parcel_id,
       ST_DistanceSphere(geom, ST_PointFromText('POINT(37.15 34.85)', 4326)) AS dist_m
FROM parcels
WHERE ST_DistanceSphere(geom, ST_PointFromText('POINT(37.15 34.85)', 4326)) < 500
ORDER BY dist_m
LIMIT 10;
```

**Note**: `ST_DistanceSphere` is NOT indexable. For large tables, pre-filter with `MBRIntersects` against a buffered bounding box:

```sql
SELECT id, parcel_id, dist_m FROM (
  SELECT id, parcel_id,
         ST_DistanceSphere(geom, @origin) AS dist_m
  FROM parcels
  WHERE MBRIntersects(geom, ST_Buffer(@origin, 0.005))  -- rough degree buffer
) candidates
WHERE dist_m < 500
ORDER BY dist_m
LIMIT 10;
```

### Spatial join

```sql
SELECT p.parcel_id, b.building_id
FROM parcels p
JOIN buildings b ON ST_Intersects(p.geom, b.geom);
```

Add `MBRIntersects` first if the optimizer doesn't use the index:

```sql
WHERE MBRIntersects(p.geom, b.geom)
  AND ST_Intersects(p.geom, b.geom);
```

## TypeORM (NestJS) entity

```typescript
import { Entity, PrimaryGeneratedColumn, Column, Index } from 'typeorm';
import { Polygon } from 'geojson';

@Entity('parcels')
export class Parcel {
  @PrimaryGeneratedColumn('increment')
  id: number;

  @Column({ unique: true })
  parcelId: string;

  @Index({ spatial: true })
  @Column({
    type: 'polygon',
    nullable: false,
    srid: 4326,
  })
  geom: Polygon;
}
```

When using MySQL with TypeORM, ensure `mysql2` driver is installed and the connection includes `supportBigNumbers: true` for large geometry rows.

## SQLAlchemy (FastAPI) model

```python
from sqlalchemy import Column, BigInteger, String, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from geoalchemy2 import Geometry

Base = declarative_base()

class Parcel(Base):
    __tablename__ = "parcels"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    parcel_id = Column(String(64), unique=True, nullable=False)
    area_sqm = Column(Float)
    zone = Column(String(64))
    geom = Column(Geometry(geometry_type="POLYGON", srid=4326), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
```

GeoAlchemy2 works with MySQL since v0.13 — confirm version when generating templates.

## Differences from PostGIS — quick callouts

| Feature | PostGIS | MySQL 8 |
|---|---|---|
| Geography type (geodesic) | Yes | No |
| `ST_Transform` | Always available | Requires PROJ install on server |
| `ST_Buffer` in meters | Cast to `geography` | Reproject to UTM first |
| `ST_MakeValid` | Yes | Yes (8.0.18+) but less robust |
| Geodesic area | `ST_Area(geom::geography)` | Reproject + `ST_Area` |
| 3D operations | Extensive (Z, M support) | Limited (mostly 2D-only) |
| Index types | GIST, SP-GIST, BRIN | R-tree only |
| `&&` bounding-box operator | Yes (operator) | `MBRIntersects` (function) |

## Common errors

| Error | Cause | Fix |
|---|---|---|
| `Cannot get geometry object from data you send to the GEOMETRY field` | SRID mismatch on insert | Use `ST_GeomFromGeoJSON(..., 2, 4326)` with explicit SRID |
| `The geometry has an unknown EPSG SRID code` | SRID not registered in `st_spatial_reference_systems` | Use 4326 (always present) or insert custom SRID into the system table |
| `A SPATIAL index may only contain a geometrical type column` | Trying to index a non-spatial column | Recheck column type |
| `All parts to a SPATIAL index must be NOT NULL` | Index column allows NULL | `ALTER TABLE ... MODIFY geom POLYGON NOT NULL SRID 4326` |
| Slow `ST_Intersects` on large tables | Index not used | Add `MBRIntersects` filter; verify `EXPLAIN` shows `range` access |

# MongoDB Geospatial Reference

MongoDB supports geospatial data as embedded **GeoJSON** in documents, indexed by **2dsphere** (or legacy **2d**) for spatial queries. No CRS handling beyond EPSG:4326 — MongoDB assumes all coordinates are WGS84 longitude-latitude.

## Document schema

GeoJSON is embedded directly under a field name (conventionally `location`, `geometry`, or `geom`):

```json
{
  "_id": ObjectId("..."),
  "parcel_id": "P-001",
  "area_sqm": 1247.5,
  "zone": "residential",
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [
        [37.1, 34.8],
        [37.2, 34.8],
        [37.2, 34.9],
        [37.1, 34.9],
        [37.1, 34.8]
      ]
    ]
  },
  "created_at": ISODate("2026-05-18T10:00:00Z")
}
```

### Allowed GeoJSON types

| Type | Use |
|---|---|
| `Point` | Single location |
| `MultiPoint` | Multiple locations as one feature |
| `LineString` | Road, path, route |
| `MultiLineString` | Disconnected line collection |
| `Polygon` | Land parcel, building footprint |
| `MultiPolygon` | Disjoint polygons as one feature (e.g., islands of a country) |
| `GeometryCollection` | Mixed types — supported but avoid; harder to index |

## **The #1 Rule: Coordinate Order is `[longitude, latitude]`**

This is the most common bug. MongoDB GeoJSON coordinates are **`[lng, lat]`**, never `[lat, lng]`:

```javascript
// CORRECT (Damascus, Syria)
{ "type": "Point", "coordinates": [36.30, 33.51] }   // lng=36.30, lat=33.51

// WRONG — points end up in the Indian Ocean
{ "type": "Point", "coordinates": [33.51, 36.30] }
```

If a query "should match documents in Syria" returns documents in the Indian Ocean, **swap the order**.

## Indexes

### 2dsphere — the default

```javascript
db.parcels.createIndex({ geometry: "2dsphere" });
```

Required for:

- `$geoWithin` with `$geometry` (GeoJSON query shape)
- `$geoIntersects`
- `$near` and `$nearSphere`
- `$geoNear` aggregation stage

Index version 3 (default since MongoDB 3.2) supports all GeoJSON types.

### 2d — legacy, avoid

Only for legacy applications using `[lng, lat]` raw arrays without GeoJSON wrapper. Skip in new designs.

### Compound 2dsphere indexes

```javascript
// Geo + filter — for "parcels in this zone within this bbox" queries
db.parcels.createIndex({ zone: 1, geometry: "2dsphere" });
```

The non-geo field should come **before** the 2dsphere field in the index — MongoDB uses the prefix for filtering, then evaluates geo.

## Query patterns

### Point-in-polygon (find documents whose geometry contains a point)

```javascript
db.parcels.find({
  geometry: {
    $geoIntersects: {
      $geometry: {
        type: "Point",
        coordinates: [37.15, 34.85]   // lng, lat
      }
    }
  }
});
```

### Find documents within a bounding box

```javascript
db.parcels.find({
  geometry: {
    $geoWithin: {
      $geometry: {
        type: "Polygon",
        coordinates: [[
          [37.0, 34.5],
          [37.5, 34.5],
          [37.5, 35.0],
          [37.0, 35.0],
          [37.0, 34.5]
        ]]
      }
    }
  }
});
```

### Find documents within N meters of a point

```javascript
db.parcels.find({
  geometry: {
    $near: {
      $geometry: {
        type: "Point",
        coordinates: [37.15, 34.85]
      },
      $maxDistance: 500    // meters
    }
  }
});
```

`$near` returns results sorted by distance (closest first). `$nearSphere` is identical for 2dsphere indexes; prefer `$near` for clarity.

### `$geoNear` aggregation stage (returns distance)

```javascript
db.parcels.aggregate([
  {
    $geoNear: {
      near: { type: "Point", coordinates: [37.15, 34.85] },
      distanceField: "dist_m",
      maxDistance: 1000,
      spherical: true
    }
  },
  { $limit: 10 }
]);
```

`$geoNear` MUST be the first stage of the pipeline and the collection MUST have exactly one 2dsphere index.

### Intersection of two polygons

```javascript
db.parcels.find({
  geometry: {
    $geoIntersects: {
      $geometry: <other_polygon_geojson>
    }
  }
});
```

There is no built-in operator for spatial join across two collections — application code or `$lookup` aggregation is required.

## Mongoose schema (Node.js)

```javascript
const parcelSchema = new mongoose.Schema({
  parcel_id: { type: String, unique: true, required: true },
  area_sqm: Number,
  zone: String,
  geometry: {
    type: { type: String, enum: ["Polygon", "MultiPolygon"], required: true },
    coordinates: { type: [[[Number]]], required: true }
  },
  created_at: { type: Date, default: Date.now }
});

parcelSchema.index({ geometry: "2dsphere" });

const Parcel = mongoose.model("Parcel", parcelSchema);
```

## Motor / PyMongo (Python)

```python
import motor.motor_asyncio
import pymongo
from bson.son import SON

client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
db = client.realestate
parcels = db.parcels

# Create index (one-time, idempotent)
await parcels.create_index([("geometry", pymongo.GEOSPHERE)])

# Insert
await parcels.insert_one({
    "parcel_id": "P-001",
    "area_sqm": 1247.5,
    "zone": "residential",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[37.1, 34.8], [37.2, 34.8], [37.2, 34.9], [37.1, 34.9], [37.1, 34.8]]]
    }
})

# Spatial query
async for doc in parcels.find({
    "geometry": {
        "$near": {
            "$geometry": {"type": "Point", "coordinates": [37.15, 34.85]},
            "$maxDistance": 500
        }
    }
}):
    print(doc)
```

## Bulk insert from a GIS file

```python
import asyncio, fiona
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform as shapely_transform

async def ingest_shapefile(path: str, target_srid: int = 4326):
    with fiona.open(path) as src:
        transformer = Transformer.from_crs(
            src.crs, f"EPSG:{target_srid}", always_xy=True
        ).transform

        batch = []
        async for_each = 1000  # batch size for insertMany
        for feature in src:
            geom = shapely_transform(transformer, shape(feature["geometry"]))
            doc = {
                **feature["properties"],
                "geometry": mapping(geom),
            }
            batch.append(doc)
            if len(batch) >= 1000:
                await parcels.insert_many(batch, ordered=False)
                batch = []
        if batch:
            await parcels.insert_many(batch, ordered=False)
```

`ordered=False` continues on duplicate-key errors instead of aborting the entire batch.

## Validation rules (optional — server-side)

```javascript
db.runCommand({
  collMod: "parcels",
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["parcel_id", "geometry"],
      properties: {
        parcel_id: { bsonType: "string" },
        geometry: {
          bsonType: "object",
          required: ["type", "coordinates"],
          properties: {
            type: { enum: ["Polygon", "MultiPolygon"] },
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

Server-side validation catches malformed GeoJSON at insert time. Pair with application-side validation for clean error messages.

## Coordinate limits and edge cases

- **Antimeridian crossing**: A polygon spanning longitude 180°/-180° must be split or use the `crs.type: "name"` extension with `urn:x-mongodb:crs:strictwinding:EPSG:4326`. MongoDB ≥ 4.0 handles strict-winding GeoJSON correctly.
- **Polar regions**: Geometries near the poles can fail 2dsphere validation if polygon rings are wound incorrectly. Use `ST_MakeValid` upstream (in PostGIS) or `shapely.geometry.polygon.orient(geom, sign=1.0)` to enforce right-hand rule.
- **Self-intersecting polygons**: Rejected by 2dsphere index validation. Fix with `shapely.make_valid()` or `geom.buffer(0)` before insert.
- **Maximum coordinate precision**: MongoDB stores BSON doubles — about 15 significant digits. Coordinates with 8 decimal places (~1 mm precision at the equator) round-trip cleanly.

## Common errors

| Error | Cause | Fix |
|---|---|---|
| `Can't extract geo keys: ... longitude/latitude is out of bounds` | Coordinates outside [-180, 180] / [-90, 90] | Reproject to EPSG:4326 first |
| `Loop is not valid: Edge X has duplicate vertex with edge Y` | Self-intersecting polygon | `shapely.make_valid()` or `geom.buffer(0)` |
| `Polygon has too few vertices` | Ring has fewer than 4 points (3 unique + 1 closing) | Fix or drop the feature |
| `more than one 2dsphere index` | Multiple geo indexes on the collection | Drop unused ones — `$geoNear` requires exactly one |
| `index not found` (on `$near`) | Missing 2dsphere index | `db.<col>.createIndex({ geometry: "2dsphere" })` |

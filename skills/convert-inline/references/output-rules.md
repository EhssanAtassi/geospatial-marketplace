# Output Formatting Rules

Per-DB-target rules for how `gis_convert.py` serializes geometry and attribute values. These rules are normative — deviations cause silent ingestion failures.

## Common rules (all targets)

1. **Geometry is always serialized to GeoJSON first**, then wrapped for the target. This keeps the script's internal model consistent.
2. **Reprojection happens before serialization.** When the source CRS is set (via `--source-crs` or detected from the file), geometries are reprojected via `pyproj.Transformer(..., always_xy=True)` to the target SRID *before* GeoJSON serialization. Coordinates in the output are always `[lng, lat]` for EPSG:4326 outputs.
3. **NULL handling**: missing or `None` attribute values become `NULL` (SQL) or `null` (JSON). The script does NOT drop the column.
4. **Encoding**: all output is UTF-8. Single quotes in attribute values are escaped per-target (SQL: `''` doubling; JSON: standard `\` escaping).
5. **Identifiers** (table/column names) are validated against `^[a-zA-Z_][a-zA-Z0-9_]*$`. Identifiers that don't match are double-quoted (PostGIS/MySQL) — backticks would be MySQL-specific so the script standardizes on ANSI double-quotes. Set `sql_mode='ANSI_QUOTES'` in MySQL when running the output if your default mode rejects them.
6. **One INSERT per feature** for SQL targets (no multi-row VALUES). Reasons: simpler error recovery, easier to truncate for chat output, cleaner diff when re-running.

## PostGIS target

### INSERT format

```sql
INSERT INTO <table> (<col1>, <col2>, ..., geom)
VALUES (<val1>, <val2>, ..., ST_GeomFromGeoJSON('<geojson_string>'));
```

- Geometry is wrapped with `ST_GeomFromGeoJSON()`. The function returns a `geometry` value with SRID 4326 by default. The schema's column type (e.g. `geometry(MultiPolygon, 4326)`) enforces SRID and type.
- The GeoJSON string is **single-line** and JSON-compact (no indent).
- If the target SRID is not 4326 and the source coords are 4326, the script does NOT auto-wrap with `ST_Transform`. That's a downstream concern — use the `--target-srid 4326` default unless storage in another SRID is genuinely required.

### DDL emitted with `--ddl`

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS <table> (
  id BIGSERIAL PRIMARY KEY,
  <col1> <type1>,
  <col2> <type2>,
  ...
  geom geometry(Geometry, <srid>) NOT NULL
  ,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS <table>_geom_gist ON <table> USING GIST (geom);
```

Notes:

- **`geometry(Geometry, <srid>)`** is intentionally polymorphic — the column accepts Point, LineString, Polygon, etc. For homogeneous datasets, change to `geometry(MultiPolygon, <srid>)` post-hoc.
- **GIST index** is always emitted. No exceptions.
- **No SRID CHECK constraint** in the auto-generated DDL — the column-level SRID enforcement already covers it.

### Attribute type mapping (fiona → PostgreSQL)

| fiona type | Postgres type |
|---|---|
| `str` / `str:N` | `TEXT` |
| `int` | `BIGINT` |
| `float` | `DOUBLE PRECISION` |
| `bool` | `BOOLEAN` |
| `date` | `DATE` |
| `datetime` | `TIMESTAMPTZ` |
| `time` | `TIME` |
| (unknown) | `TEXT` |

## MySQL spatial target

### INSERT format

```sql
INSERT INTO <table> (<col1>, ..., geom)
VALUES (<val1>, ..., ST_GeomFromGeoJSON('<geojson>', 2, <srid>));
```

- The second argument `2` allows higher-dimension (Z, M) coordinates and silently drops them. This matters for DWG/DXF inputs where Z=0 is common.
- The third argument is the explicit SRID. MySQL is strict about SRID matching with the column declaration.

### DDL emitted with `--ddl`

```sql
CREATE TABLE IF NOT EXISTS <table> (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  <col1> <type1>,
  ...
  geom GEOMETRY NOT NULL SRID <srid>
  ,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE SPATIAL INDEX <table>_geom_idx ON <table> (geom);
```

Notes:

- **`GEOMETRY` (polymorphic)** instead of a specific type. Same reasoning as PostGIS.
- **`SRID <srid>` is non-negotiable** — MySQL 8 R-tree indexes require it.
- **Spatial index column must be NOT NULL** — enforced.

### Attribute type mapping (fiona → MySQL)

| fiona type | MySQL type |
|---|---|
| `str:N` (N specified) | `VARCHAR(N)` |
| `str` (no length) | `TEXT` |
| `int` | `BIGINT` |
| `float` | `DOUBLE` |
| `bool` | `TINYINT(1)` |
| `date` | `DATE` |
| `datetime` | `TIMESTAMP` |
| `time` | `TIME` |
| (unknown) | `TEXT` |

## MongoDB target

### Document format

```javascript
db.<collection>.insertMany([
  {"prop1": ..., "prop2": ..., "geometry": {"type": "Polygon", "coordinates": [...]}},
   ,{"prop1": ..., ...},
   ,...
]);
```

Notes:

- **Geometry is embedded as native GeoJSON** under the `geometry` field name. The field name is intentionally non-customizable in v0.1 — most MongoDB GeoJSON tutorials use it.
- **Coordinate order is `[lng, lat]`** universally (MongoDB GeoJSON requirement). Reprojection to 4326 happens regardless of `--target-srid` because 2dsphere indexes only support 4326.
- **Properties are spread at the document root**, not nested under `properties`. This is more idiomatic for MongoDB documents than mirroring GeoJSON Feature structure.
- **Output uses `default=str`** for `json.dumps` so dates and other non-JSON-native values serialize as ISO strings.

### Comma placement

The "leading-comma" style (`,{...}`) is intentional:

- First document is indented `  ` (two spaces).
- Subsequent documents are prefixed with ` ,` (space + comma).
- Makes per-line diffs cleaner than trailing commas and keeps each document line-addressable.

If your downstream tooling rejects this style, run `sed 's/^ ,/,/' file.js` to normalize.

### DDL emitted with `--ddl`

```javascript
db.<collection>.createIndex({ "geometry": "2dsphere" });
```

That's it. MongoDB collections are implicit — no `CREATE COLLECTION` needed. The `insertMany()` call creates the collection automatically if it doesn't exist.

If `--target-srid` is not 4326, the output begins with a warning comment:

```javascript
// ⚠ MongoDB requires EPSG:4326 for 2dsphere indexes. Requested SRID <n> will be ignored — geometries reprojected to 4326.
```

## Truncation rules (chat output)

The script writes the **full** output to `/tmp/<table-name>.{sql,js}` and prints only a **truncated** version to stdout for chat readability. The truncation rules:

1. The first `--limit N` (default 100) INSERT statements or document entries are printed verbatim.
2. After hitting the limit, ONE truncation-hint line is printed, then no more body output. The full output continues to the file.
3. DDL (when `--ddl` is set) is always printed in full — it's never truncated.
4. Headers (source, format, target, full-output-path, feature count) and footer (run command) are always printed.

Truncation-hint line format:

```
-- ⚠ Output truncated to <limit> features for chat readability. Full output saved to <full_path>.
```

(`//` comment marker for MongoDB targets instead of `--`.)

## Footer

The footer prints a ready-to-run command:

| Target | Footer command |
|---|---|
| postgis | `-- Run with: psql <connection-string> -f /tmp/<table>.sql` |
| mysql | `-- Run with: mysql <connection-string> < /tmp/<table>.sql` |
| mongo | `// Run with: mongosh <connection-string> /tmp/<table>.js` |

The `<connection-string>` placeholder is literal — the script does NOT substitute the user's DB URI even if it's available in settings. This is deliberate: the script never sees DB credentials, and the user reviews the output before connecting to anything.

## Encoding edge cases

- **Non-ASCII attribute values** (Arabic names, Cyrillic text, Chinese characters) — JSON output uses `ensure_ascii=False` so the characters appear directly. SQL output uses the same approach via standard string escaping. Both work in UTF-8 client connections; if your client is in another encoding, transcode the output file.
- **NULL bytes in attribute values** — possible in malformed Shapefiles. The script does NOT sanitize these; they'll fail at INSERT time. To pre-filter, run the file through `iconv -c -f UTF-8 -t UTF-8` first.
- **Very long attribute values** (>1MB cell) — possible in `BLOB`-typed Shapefile fields. The script writes them as-is into the SQL, which may break some shells when piping. Always prefer file-based execution (`psql -f`).

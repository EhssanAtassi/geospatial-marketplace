#!/usr/bin/env python3
"""GIS / CAD file → SQL or MongoDB documents (in-chat output).

Reads a Shapefile, ESRI File Geodatabase, GeoJSON, KML, DXF, or DWG file,
reprojects geometries to a target SRID (default 4326), and emits one of:

- PostGIS INSERT statements (--target postgis)
- MySQL spatial INSERT statements (--target mysql)
- MongoDB insertMany() call (--target mongo)

Optionally emits DDL (CREATE TABLE / index / 2dsphere index) when --ddl is set.
Writes the full output to /tmp/<table>.{sql,js} AND prints the chat-truncated
portion (limited to --limit features) to stdout.

Usage:
    python gis_convert.py <path> --target postgis --table-name parcels [--ddl] [--limit 100] [--source-crs EPSG:32637] [--target-srid 4326] [--layer LAYER]

Exit codes:
    0  success
    1  user error (file not found, missing required arg, unsupported format)
    2  internal error (parser/reprojection failure)
    3  required tooling missing (GDAL, ezdxf, LibreDWG)
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TARGET_SRID = 4326
DEFAULT_LIMIT = 100
CHAT_TRUNCATE_HINT = (
    "-- ⚠ Output truncated to {limit} features for chat readability. "
    "Full output saved to {full_path}."
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a GIS or CAD file to SQL inserts or MongoDB documents."
    )
    parser.add_argument("path", help="Path to file or .gdb directory")
    parser.add_argument(
        "--target",
        required=True,
        choices=["postgis", "mongo", "mysql"],
        help="Target database flavour",
    )
    parser.add_argument(
        "--table-name", required=True, help="Target table or collection name"
    )
    parser.add_argument(
        "--target-srid",
        type=int,
        default=DEFAULT_TARGET_SRID,
        help=f"Target SRID for reprojection (default {DEFAULT_TARGET_SRID})",
    )
    parser.add_argument(
        "--source-crs",
        help="Override source CRS (e.g. EPSG:32637). Required for DWG/DXF without CRS.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Max features to include in chat output (default {DEFAULT_LIMIT})",
    )
    parser.add_argument("--ddl", action="store_true", help="Emit CREATE TABLE / index DDL")
    parser.add_argument("--layer", help="Layer name (for multi-layer formats)")
    parser.add_argument(
        "--full-output-dir",
        default="/tmp",
        help="Directory for the full (untruncated) output file (default /tmp)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Format detection (shared with gis_inspect)
# ---------------------------------------------------------------------------


def detect_format(path: Path) -> tuple[str, str]:
    if path.is_dir() and any(path.glob("*.gdbtable")):
        return "ESRI File Geodatabase", "OpenFileGDB"
    suffix = path.suffix.lower()
    return {
        ".shp": ("Shapefile", "ESRI Shapefile"),
        ".geojson": ("GeoJSON", "GeoJSON"),
        ".json": ("GeoJSON", "GeoJSON"),
        ".kml": ("KML", "LIBKML"),
        ".kmz": ("KMZ", "LIBKML"),
        ".gpkg": ("GeoPackage", "GPKG"),
        ".dxf": ("DXF", "__ezdxf__"),
        ".dwg": ("DWG", "__libredwg__"),
    }.get(suffix, ("Unknown", "Unknown"))


# ---------------------------------------------------------------------------
# Feature reader (yields dicts with `geometry` (GeoJSON) and `properties`)
# ---------------------------------------------------------------------------


def read_fiona(path: Path, driver: str, layer: str | None) -> Iterable[dict[str, Any]]:
    import fiona  # type: ignore

    with fiona.open(str(path), layer=layer, driver=driver) as src:
        for feature in src:
            # fiona >= 1.10 returns fiona.Geometry / fiona.Properties wrappers
            # instead of plain dicts. Normalize so downstream json.dumps() and
            # dict iteration work for both legacy and current fiona releases.
            geom = feature["geometry"]
            if geom is not None and not isinstance(geom, dict):
                geom = (
                    dict(geom.__geo_interface__)
                    if hasattr(geom, "__geo_interface__")
                    else dict(geom)
                )
            props = feature["properties"]
            props_dict = dict(props) if props else {}
            yield {
                "geometry": geom,
                "properties": props_dict,
                "source_crs": src.crs,
            }


def read_dxf(path: Path, layer_filter: str | None) -> Iterable[dict[str, Any]]:
    import ezdxf  # type: ignore
    from shapely.geometry import LineString, Point, Polygon, mapping  # type: ignore

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    for entity in msp:
        layer = entity.dxf.layer
        if layer_filter and layer != layer_filter:
            continue
        geom = _dxf_entity_to_geom(entity)
        if geom is None:
            continue
        yield {
            "geometry": mapping(geom),
            "properties": {"layer": layer, "dxftype": entity.dxftype()},
            "source_crs": None,
        }


def _dxf_entity_to_geom(entity: Any) -> Any:
    from shapely.geometry import LineString, Point, Polygon  # type: ignore

    dxftype = entity.dxftype()
    if dxftype == "POINT":
        loc = entity.dxf.location
        return Point(loc.x, loc.y)
    if dxftype == "LINE":
        start, end = entity.dxf.start, entity.dxf.end
        return LineString([(start.x, start.y), (end.x, end.y)])
    if dxftype == "LWPOLYLINE":
        points = [(p[0], p[1]) for p in entity.get_points()]
        if entity.closed and len(points) >= 3:
            return Polygon(points)
        return LineString(points) if len(points) >= 2 else None
    if dxftype == "POLYLINE":
        points = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
        if entity.is_closed and len(points) >= 3:
            return Polygon(points)
        return LineString(points) if len(points) >= 2 else None
    if dxftype == "CIRCLE":
        center = entity.dxf.center
        cx, cy = center.x, center.y
        r = entity.dxf.radius
        points = [
            (cx + r * math.cos(i * 2 * math.pi / 64), cy + r * math.sin(i * 2 * math.pi / 64))
            for i in range(64)
        ]
        return Polygon(points)
    if dxftype == "ARC":
        center = entity.dxf.center
        cx, cy = center.x, center.y
        r = entity.dxf.radius
        start_a = math.radians(entity.dxf.start_angle)
        end_a = math.radians(entity.dxf.end_angle)
        if end_a < start_a:
            end_a += 2 * math.pi
        steps = max(16, int((end_a - start_a) / (math.pi / 32)))
        return LineString(
            [
                (cx + r * math.cos(start_a + i * (end_a - start_a) / steps),
                 cy + r * math.sin(start_a + i * (end_a - start_a) / steps))
                for i in range(steps + 1)
            ]
        )
    return None  # Skip unsupported types


def read_dwg(path: Path, layer_filter: str | None) -> Iterable[dict[str, Any]]:
    if not shutil.which("dwg2dxf"):
        raise RuntimeError(
            "LibreDWG (dwg2dxf) not installed. Install with: apt-get install "
            "libredwg-tools, or run inside Docker (osgeo/gdal:ubuntu-small + "
            "libredwg-tools)."
        )
    with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            ["dwg2dxf", "-o", str(tmp_path), str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"LibreDWG conversion failed: {result.stderr.strip()[:300]}"
            )
        yield from read_dxf(tmp_path, layer_filter)
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Reprojection
# ---------------------------------------------------------------------------


def reproject_geometry(
    geom_geojson: dict[str, Any] | None,
    source_crs: Any,
    target_srid: int,
) -> dict[str, Any] | None:
    """Reproject a GeoJSON-shaped geometry from source_crs to EPSG:<target_srid>.

    Returns None unchanged for features with null geometry — these are valid
    in OGR/fiona data (an "attribute-only" row) and must not crash the
    reprojection pipeline.
    """
    if geom_geojson is None:
        return None
    if not source_crs:
        return geom_geojson
    try:
        from pyproj import Transformer  # type: ignore
        from shapely.geometry import mapping, shape  # type: ignore
        from shapely.ops import transform as shapely_transform  # type: ignore
    except ImportError as exc:
        raise RuntimeError(f"pyproj/shapely required: {exc}") from exc

    # Normalize source_crs to something pyproj's Transformer accepts unambiguously.
    # fiona 1.10 returns CRS objects, fiona <1.10 returned dicts, callers may
    # also pass plain "EPSG:N" strings. Convert each form to a WKT or EPSG string.
    if isinstance(source_crs, str):
        src_for_pyproj: Any = source_crs
    elif hasattr(source_crs, "to_wkt"):
        src_for_pyproj = source_crs.to_wkt()
    elif hasattr(source_crs, "to_string"):
        src_for_pyproj = source_crs.to_string()
    elif isinstance(source_crs, dict):
        src_for_pyproj = source_crs.get("init") or str(source_crs)
    else:
        src_for_pyproj = str(source_crs)
    transformer = Transformer.from_crs(
        src_for_pyproj, f"EPSG:{target_srid}", always_xy=True
    )
    geom = shape(geom_geojson)
    new_geom = shapely_transform(transformer.transform, geom)
    return mapping(new_geom)


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


SAFE_SQL_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Reserved column names used by the schema. Properties matching these
# (case-insensitive) are renamed in the output to avoid SQL collisions.
RESERVED_COLUMNS = {"geom", "geog", "geometry"}


def _disambiguate_props(props: dict[str, Any]) -> dict[str, Any]:
    """Rename any property whose name collides with our reserved schema columns.

    Example: an attribute literally named `geom` in the input becomes `geom_attr`
    in the SQL output, preventing INSERT INTO t (geom, geom) VALUES (...).
    """
    if not any(k.lower() in RESERVED_COLUMNS for k in props):
        return props
    renamed: dict[str, Any] = {}
    for k, v in props.items():
        if k.lower() in RESERVED_COLUMNS:
            new_key = f"{k}_attr"
            # Avoid double-collision if `geom_attr` is also present
            while new_key in props or new_key in renamed:
                new_key += "_"
            renamed[new_key] = v
        else:
            renamed[k] = v
    return renamed


def _safe_ident(name: str) -> str:
    """Quote SQL identifiers safely. Plain identifiers are returned unquoted."""
    if SAFE_SQL_IDENT.match(name):
        return name
    return '"' + name.replace('"', '""') + '"'


def _sql_value(v: Any) -> str:
    """Serialize a Python value into a SQL literal."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    # Treat everything else as text
    return "'" + str(v).replace("'", "''") + "'"


def format_postgis(
    features: Iterable[dict[str, Any]],
    table_name: str,
    target_srid: int,
    emit_ddl: bool,
    attribute_schema: dict[str, str] | None = None,
) -> Iterable[str]:
    """Yield PostGIS-flavoured SQL lines."""
    table = _safe_ident(table_name)
    if emit_ddl and attribute_schema is not None:
        # Disambiguate schema field names that collide with reserved columns.
        attribute_schema = _disambiguate_props(attribute_schema)
        yield f"-- PostGIS DDL for {table}"
        yield "CREATE EXTENSION IF NOT EXISTS postgis;"
        col_lines = [f"  id BIGSERIAL PRIMARY KEY"]
        for fname, ftype in attribute_schema.items():
            col_lines.append(f"  {_safe_ident(fname)} {_map_postgres_type(ftype)}")
        col_lines.append(f"  geom geometry(Geometry, {target_srid}) NOT NULL")
        col_lines.append(f"  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        yield f"CREATE TABLE IF NOT EXISTS {table} ("
        yield ",\n".join(col_lines)
        yield ");"
        yield f"CREATE INDEX IF NOT EXISTS {table_name}_geom_gist ON {table} USING GIST (geom);"
        yield ""

    for feature in features:
        props = _disambiguate_props(feature["properties"])
        geom_geojson = feature["geometry"]
        if not geom_geojson:
            continue
        cols = [_safe_ident(k) for k in props.keys()] + ["geom"]
        vals = [_sql_value(v) for v in props.values()] + [
            f"ST_GeomFromGeoJSON('{json.dumps(geom_geojson)}')"
        ]
        yield f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(vals)});"


def format_mysql(
    features: Iterable[dict[str, Any]],
    table_name: str,
    target_srid: int,
    emit_ddl: bool,
    attribute_schema: dict[str, str] | None = None,
) -> Iterable[str]:
    table = _safe_ident(table_name)
    if emit_ddl and attribute_schema is not None:
        attribute_schema = _disambiguate_props(attribute_schema)
        yield f"-- MySQL spatial DDL for {table}"
        col_lines = [f"  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY"]
        for fname, ftype in attribute_schema.items():
            col_lines.append(f"  {_safe_ident(fname)} {_map_mysql_type(ftype)}")
        col_lines.append(f"  geom GEOMETRY NOT NULL SRID {target_srid}")
        col_lines.append(f"  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        yield f"CREATE TABLE IF NOT EXISTS {table} ("
        yield ",\n".join(col_lines)
        yield ");"
        yield f"CREATE SPATIAL INDEX {table_name}_geom_idx ON {table} (geom);"
        yield ""

    for feature in features:
        props = _disambiguate_props(feature["properties"])
        geom_geojson = feature["geometry"]
        if not geom_geojson:
            continue
        cols = [_safe_ident(k) for k in props.keys()] + ["geom"]
        vals = [_sql_value(v) for v in props.values()] + [
            f"ST_GeomFromGeoJSON('{json.dumps(geom_geojson)}', 2, {target_srid})"
        ]
        yield f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(vals)});"


def format_mongo(
    features: Iterable[dict[str, Any]],
    collection_name: str,
    target_srid: int,  # always 4326 for MongoDB, but accept for API symmetry
    emit_ddl: bool,
    attribute_schema: dict[str, str] | None = None,
) -> Iterable[str]:
    if target_srid != 4326:
        yield (
            "// ⚠ MongoDB requires EPSG:4326 for 2dsphere indexes. "
            f"Requested SRID {target_srid} will be ignored — geometries reprojected to 4326."
        )
    if emit_ddl:
        yield f"// MongoDB index for {collection_name}"
        yield f'db.{collection_name}.createIndex({{ "geometry": "2dsphere" }});'
        yield ""

    yield f"db.{collection_name}.insertMany(["
    first = True
    for feature in features:
        # MongoDB uses `geometry` as the reserved key — disambiguate any
        # source attribute named `geometry`, `geom`, or `geog`.
        props = _disambiguate_props(feature["properties"])
        geom_geojson = feature["geometry"]
        if not geom_geojson:
            continue
        doc = {**props, "geometry": geom_geojson}
        prefix = "  " if first else " ,"
        first = False
        yield prefix + json.dumps(doc, default=str, ensure_ascii=False)
    yield "]);"


# ---------------------------------------------------------------------------
# Type mapping (fiona schema → SQL types)
# ---------------------------------------------------------------------------


def _normalize_fiona_base_type(base: str) -> str:
    """fiona schema types come as 'int32', 'int64', 'int', 'float', 'float64',
    'str', etc. Normalize to a small set ('int', 'float', 'str', ...) so the
    type maps below match real-world inputs (Shapefile DBF fields commonly
    arrive as 'int32:9' or 'float:19.11')."""
    if base.startswith("int"):
        return "int"
    if base.startswith("float") or base.startswith("double"):
        return "float"
    return base


def _map_postgres_type(fiona_type: str) -> str:
    base = _normalize_fiona_base_type(fiona_type.split(":")[0].lower())
    return {
        "str": "TEXT",
        "int": "BIGINT",
        "float": "DOUBLE PRECISION",
        "bool": "BOOLEAN",
        "date": "DATE",
        "datetime": "TIMESTAMPTZ",
        "time": "TIME",
    }.get(base, "TEXT")


def _map_mysql_type(fiona_type: str) -> str:
    parts = fiona_type.split(":")
    base = _normalize_fiona_base_type(parts[0].lower())
    length = parts[1] if len(parts) > 1 else None
    if base == "str":
        return f"VARCHAR({length})" if length else "TEXT"
    return {
        "int": "BIGINT",
        "float": "DOUBLE",
        "bool": "TINYINT(1)",
        "date": "DATE",
        "datetime": "TIMESTAMP",
        "time": "TIME",
    }.get(base, "TEXT")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()
    path = Path(args.path).resolve()
    if not path.exists():
        print(json.dumps({"error": "file not found"}), file=sys.stderr)
        return 1
    fmt, driver = detect_format(path)
    if fmt == "Unknown":
        print(json.dumps({"error": "unsupported format"}), file=sys.stderr)
        return 1

    # Schema introspection (fiona only — DXF/DWG don't have a schema)
    attribute_schema: dict[str, str] | None = None
    if driver not in ("__ezdxf__", "__libredwg__") and args.ddl:
        try:
            import fiona  # type: ignore

            with fiona.open(str(path), layer=args.layer, driver=driver) as src:
                attribute_schema = dict(src.schema.get("properties", {}))
        except ImportError:
            print(
                json.dumps({"error": "fiona required for DDL emission"}),
                file=sys.stderr,
            )
            return 3
        except Exception as exc:
            print(json.dumps({"error": f"DDL introspection failed: {exc}"}), file=sys.stderr)
            return 2

    # Read features
    try:
        if driver == "__ezdxf__":
            features_raw = read_dxf(path, args.layer)
        elif driver == "__libredwg__":
            features_raw = read_dwg(path, args.layer)
        else:
            features_raw = read_fiona(path, driver, args.layer)
    except ImportError as exc:
        print(json.dumps({"error": f"missing dependency: {exc}"}), file=sys.stderr)
        return 3
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 3

    # Reproject in-stream
    target_srid = args.target_srid if args.target != "mongo" else 4326

    def reprojected() -> Iterable[dict[str, Any]]:
        for feature in features_raw:
            src_crs = args.source_crs or feature.get("source_crs")
            if not src_crs:
                # DWG/DXF without --source-crs — pass through unprojected
                yield feature
                continue
            try:
                feature["geometry"] = reproject_geometry(
                    feature["geometry"], src_crs, target_srid
                )
            except RuntimeError as exc:
                print(json.dumps({"error": str(exc)}), file=sys.stderr)
                raise
            yield feature

    # Choose formatter
    if args.target == "postgis":
        formatter = format_postgis
        ext = ".sql"
    elif args.target == "mysql":
        formatter = format_mysql
        ext = ".sql"
    else:  # mongo
        formatter = format_mongo
        ext = ".js"

    # Write full output to /tmp and stream truncated to stdout
    full_path = Path(args.full_output_dir) / f"{args.table_name}{ext}"
    truncate_after = args.limit

    written_count = 0
    chat_lines: list[str] = []
    try:
        with full_path.open("w") as full_out:
            for line in formatter(
                reprojected(),
                args.table_name,
                target_srid,
                args.ddl,
                attribute_schema,
            ):
                full_out.write(line + "\n")
                if line.startswith("INSERT") or line.startswith("  {") or line.startswith(" ,{"):
                    written_count += 1
                if written_count <= truncate_after:
                    chat_lines.append(line)
                elif written_count == truncate_after + 1:
                    chat_lines.append(
                        CHAT_TRUNCATE_HINT.format(
                            limit=truncate_after, full_path=full_path
                        )
                    )
    except Exception as exc:
        print(json.dumps({"error": f"conversion failed: {exc}"}), file=sys.stderr)
        return 2

    # Header
    print(f"-- Source: {path}")
    print(f"-- Format: {fmt}")
    print(f"-- Target: {args.target} (SRID {target_srid})")
    print(f"-- Full output saved to: {full_path}")
    print(f"-- Features emitted: {written_count} (chat truncated to {truncate_after})")
    print()

    # Body
    print("\n".join(chat_lines))

    # Footer
    print()
    if args.target == "postgis":
        print(f"-- Run with: psql <connection-string> -f {full_path}")
    elif args.target == "mysql":
        print(f"-- Run with: mysql <connection-string> < {full_path}")
    else:  # mongo
        print(f"// Run with: mongosh <connection-string> {full_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

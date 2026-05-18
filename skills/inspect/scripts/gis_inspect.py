#!/usr/bin/env python3
"""GIS / CAD file inspector.

Reads a Shapefile, ESRI File Geodatabase, GeoJSON, KML, DXF, or DWG file
(via LibreDWG conversion) and emits a structured JSON report describing
its format, CRS, layers, geometry types, feature count, attribute schema,
and a small sample of features. Does not connect to any database and does
not modify any file outside /tmp.

Usage:
    python gis_inspect.py <path> [--json] [--features-sample N] [--layer NAME]

Exit codes:
    0  success
    1  user error (file not found, unsupported format)
    2  internal error (parser failure)
    3  required tooling missing (GDAL, LibreDWG)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class FieldInfo:
    name: str
    type: str


@dataclass
class LayerReport:
    name: str | None
    geometry_type: str | None
    feature_count: int
    crs_epsg: int | None
    crs_wkt: str | None
    bounds: tuple[float, float, float, float] | None
    fields: list[FieldInfo] = field(default_factory=list)
    sample_features: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class InspectionReport:
    path: str
    size_bytes: int
    format: str
    driver: str
    layers: list[LayerReport] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


def detect_format(path: Path) -> tuple[str, str]:
    """Return (format_name, fiona_driver_or_special)."""
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
# Environment probe
# ---------------------------------------------------------------------------


def probe_environment() -> dict[str, Any]:
    env: dict[str, Any] = {}
    # GDAL via fiona
    try:
        import fiona  # type: ignore

        env["fiona"] = fiona.__version__
        env["gdal"] = fiona.__gdal_version__
        env["fiona_drivers"] = sorted(fiona.supported_drivers.keys())
    except ImportError:
        env["fiona"] = None
        env["gdal"] = None
    # ezdxf
    try:
        import ezdxf  # type: ignore

        env["ezdxf"] = ezdxf.__version__
    except ImportError:
        env["ezdxf"] = None
    # LibreDWG
    env["libredwg"] = shutil.which("dwg2dxf") is not None
    return env


# ---------------------------------------------------------------------------
# CRS helpers
# ---------------------------------------------------------------------------


def crs_to_epsg(crs: Any) -> int | None:
    """Best-effort extraction of EPSG code from a fiona CRS object."""
    if not crs:
        return None
    if hasattr(crs, "to_epsg"):
        try:
            return crs.to_epsg()
        except Exception:
            pass
    if isinstance(crs, dict):
        init = crs.get("init", "")
        if init.lower().startswith("epsg:"):
            try:
                return int(init.split(":")[1])
            except (IndexError, ValueError):
                return None
    return None


def crs_to_wkt(crs: Any) -> str | None:
    if hasattr(crs, "to_wkt"):
        try:
            return crs.to_wkt()
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Fiona-backed inspectors (Shapefile / .gdb / GeoJSON / KML / GeoPackage)
# ---------------------------------------------------------------------------


def inspect_fiona(
    path: Path,
    driver: str,
    layer_filter: str | None,
    sample_count: int,
) -> list[LayerReport]:
    import fiona  # type: ignore
    from shapely.geometry import shape  # type: ignore

    # List layers (only meaningful for multi-layer formats)
    try:
        all_layers = fiona.listlayers(str(path))
    except Exception:
        all_layers = [None]
    if layer_filter:
        if layer_filter not in (all_layers or []) and all_layers != [None]:
            return [
                LayerReport(
                    name=layer_filter,
                    geometry_type=None,
                    feature_count=0,
                    crs_epsg=None,
                    crs_wkt=None,
                    bounds=None,
                    warnings=[
                        f"Layer '{layer_filter}' not found. Available: "
                        + ", ".join(all_layers or ["(default)"])
                    ],
                )
            ]
        layers_to_read = [layer_filter]
    else:
        layers_to_read = all_layers if all_layers else [None]

    reports: list[LayerReport] = []
    for layer in layers_to_read:
        try:
            with fiona.open(str(path), layer=layer, driver=driver) as src:
                report = LayerReport(
                    name=layer if layer is not None else None,
                    geometry_type=(src.schema or {}).get("geometry"),
                    feature_count=len(src),
                    crs_epsg=crs_to_epsg(src.crs),
                    crs_wkt=crs_to_wkt(src.crs),
                    bounds=tuple(src.bounds) if src.bounds else None,
                    fields=[
                        FieldInfo(name=n, type=t)
                        for n, t in (src.schema or {}).get("properties", {}).items()
                    ],
                )
                # Warnings
                if not src.crs:
                    report.warnings.append(
                        "No CRS detected. Reprojection target cannot be determined; "
                        "user must supply source CRS before ingestion."
                    )
                elif report.crs_epsg and report.crs_epsg != 4326:
                    report.warnings.append(
                        f"Source CRS is EPSG:{report.crs_epsg}; reprojection to "
                        "EPSG:4326 will be required for MongoDB and most web targets."
                    )
                # Sample features
                for i, feature in enumerate(src):
                    if i >= sample_count:
                        break
                    try:
                        geom = shape(feature["geometry"])
                        preview = geom.wkt[:200] + ("…" if len(geom.wkt) > 200 else "")
                    except Exception:
                        preview = "<unreadable geometry>"
                    report.sample_features.append(
                        {
                            "id": feature.get("id"),
                            "geometry_preview": preview,
                            "properties": dict(feature["properties"]),
                        }
                    )
                reports.append(report)
        except Exception as exc:
            reports.append(
                LayerReport(
                    name=layer,
                    geometry_type=None,
                    feature_count=0,
                    crs_epsg=None,
                    crs_wkt=None,
                    bounds=None,
                    warnings=[f"Failed to read layer: {exc}"],
                )
            )
    return reports


# ---------------------------------------------------------------------------
# DXF / DWG inspectors
# ---------------------------------------------------------------------------


def inspect_dxf(path: Path, sample_count: int) -> list[LayerReport]:
    try:
        import ezdxf  # type: ignore
    except ImportError:
        return [
            LayerReport(
                name=None,
                geometry_type=None,
                feature_count=0,
                crs_epsg=None,
                crs_wkt=None,
                bounds=None,
                warnings=["ezdxf not installed. Install with: pip install ezdxf"],
            )
        ]
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    layers: dict[str, dict[str, int]] = {}
    for entity in msp:
        layer = entity.dxf.layer
        dxftype = entity.dxftype()
        layers.setdefault(layer, {}).setdefault(dxftype, 0)
        layers[layer][dxftype] += 1

    reports: list[LayerReport] = []
    for layer_name, type_counts in layers.items():
        total = sum(type_counts.values())
        primary_geom = _dxf_primary_geometry_type(type_counts)
        report = LayerReport(
            name=layer_name,
            geometry_type=primary_geom,
            feature_count=total,
            crs_epsg=None,
            crs_wkt=None,
            bounds=None,
            fields=[FieldInfo(name=t, type=f"count={c}") for t, c in type_counts.items()],
            warnings=[
                "DXF/DWG has no CRS metadata. User must supply source CRS before ingestion.",
            ],
        )
        # Sample: take up to sample_count entities of the primary type
        sampled = 0
        primary_type = max(type_counts, key=type_counts.get) if type_counts else None
        if primary_type:
            for entity in msp.query(f"{primary_type}[layer=='{layer_name}']"):
                if sampled >= sample_count:
                    break
                report.sample_features.append(
                    {
                        "dxftype": primary_type,
                        "handle": entity.dxf.handle,
                        "preview": str(entity)[:200],
                    }
                )
                sampled += 1
        reports.append(report)
    if not reports:
        reports.append(
            LayerReport(
                name=None,
                geometry_type=None,
                feature_count=0,
                crs_epsg=None,
                crs_wkt=None,
                bounds=None,
                warnings=["No entities found in model space."],
            )
        )
    return reports


def _dxf_primary_geometry_type(type_counts: dict[str, int]) -> str | None:
    """Map dominant DXF entity type to a Shapely-style geometry name."""
    if not type_counts:
        return None
    primary = max(type_counts, key=type_counts.get)
    return {
        "POINT": "Point",
        "LINE": "LineString",
        "LWPOLYLINE": "Polygon|LineString",
        "POLYLINE": "Polygon|LineString",
        "POLYGON": "Polygon",
        "CIRCLE": "Polygon (approximated)",
        "ARC": "LineString (sampled)",
        "ELLIPSE": "Polygon|LineString",
        "SPLINE": "LineString (sampled)",
        "HATCH": "Polygon (boundary)",
        "TEXT": "(annotation — skipped)",
        "MTEXT": "(annotation — skipped)",
        "DIMENSION": "(annotation — skipped)",
        "INSERT": "(block reference — skipped unless expanded)",
    }.get(primary, primary)


def inspect_dwg(path: Path, sample_count: int) -> list[LayerReport]:
    """Convert DWG → DXF via LibreDWG, then inspect the DXF."""
    if not shutil.which("dwg2dxf"):
        return [
            LayerReport(
                name=None,
                geometry_type=None,
                feature_count=0,
                crs_epsg=None,
                crs_wkt=None,
                bounds=None,
                warnings=[
                    "LibreDWG (`dwg2dxf`) not installed. Install with: "
                    "apt-get install libredwg-tools — OR run inspection inside Docker "
                    "(osgeo/gdal:ubuntu-small + libredwg-tools)."
                ],
            )
        ]
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
            return [
                LayerReport(
                    name=None,
                    geometry_type=None,
                    feature_count=0,
                    crs_epsg=None,
                    crs_wkt=None,
                    bounds=None,
                    warnings=[
                        f"LibreDWG conversion failed: {result.stderr.strip()[:300]}. "
                        "Try ODA File Converter as a fallback."
                    ],
                )
            ]
        return inspect_dxf(tmp_path, sample_count)
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def build_next_steps(report: InspectionReport) -> list[str]:
    """Suggest follow-up commands based on what was inspected."""
    steps: list[str] = []
    has_crs_issue = any(
        any("No CRS detected" in w or "no CRS metadata" in w for w in layer.warnings)
        for layer in report.layers
    )
    has_features = any(layer.feature_count > 0 for layer in report.layers)

    if has_crs_issue:
        steps.append(
            "Source CRS is missing. Re-run `/gis-to-db:inspect` after the user "
            "supplies the source CRS via `--source-crs EPSG:N`."
        )
    if has_features:
        steps.append(
            "To preview SQL/MongoDB output: "
            f"`/gis-to-db:convert {report.path} --target <postgis|mongo|mysql> --limit 10`."
        )
        steps.append(
            "To scaffold a full ingestion service: "
            "`/gis-to-db:scaffold-service --db-target <target>`."
        )
        steps.append(
            "To wire ingestion into an existing app: "
            "`/gis-to-db:add-module --host-dir <path>`."
        )
    return steps


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect a GIS or CAD file.")
    parser.add_argument("path", help="Path to file or .gdb directory")
    parser.add_argument(
        "--json", action="store_true", help="Output JSON instead of markdown"
    )
    parser.add_argument(
        "--features-sample",
        type=int,
        default=3,
        help="Number of sample features per layer (default 3)",
    )
    parser.add_argument(
        "--layer",
        help="Limit inspection to a single layer (multi-layer formats only)",
    )
    return parser.parse_args()


def render_markdown(report: InspectionReport) -> str:
    out: list[str] = []
    out.append(f"# Inspection Report — `{report.path}`\n")
    out.append("## File\n")
    out.append(f"- **Format**: {report.format}")
    out.append(f"- **Driver**: {report.driver}")
    out.append(f"- **Size**: {report.size_bytes:,} bytes")
    out.append("")
    out.append("## Environment\n")
    env = report.environment
    out.append(f"- GDAL: `{env.get('gdal') or 'MISSING'}`")
    out.append(f"- fiona: `{env.get('fiona') or 'MISSING'}`")
    out.append(f"- ezdxf: `{env.get('ezdxf') or 'MISSING'}`")
    out.append(f"- LibreDWG: `{'present' if env.get('libredwg') else 'MISSING'}`")
    out.append("")
    for i, layer in enumerate(report.layers, 1):
        name = layer.name or "(default)"
        out.append(f"## Layer {i}: `{name}`\n")
        out.append(f"- Geometry: **{layer.geometry_type or 'unknown'}**")
        out.append(f"- Features: **{layer.feature_count:,}**")
        if layer.crs_epsg:
            out.append(f"- CRS: **EPSG:{layer.crs_epsg}**")
        elif layer.crs_wkt:
            out.append("- CRS: (custom WKT — see JSON output)")
        else:
            out.append("- CRS: **MISSING** — user must supply source CRS")
        if layer.bounds:
            minx, miny, maxx, maxy = layer.bounds
            out.append(
                f"- Bounds: ({minx:.6f}, {miny:.6f}) → ({maxx:.6f}, {maxy:.6f})"
            )
        if layer.fields:
            out.append("\n### Attributes\n")
            out.append("| Name | Type |")
            out.append("|---|---|")
            for f in layer.fields:
                out.append(f"| `{f.name}` | {f.type} |")
        if layer.sample_features:
            out.append("\n### Sample features\n")
            for j, feat in enumerate(layer.sample_features, 1):
                out.append(f"**Feature {j}:**")
                out.append(f"```json\n{json.dumps(feat, indent=2, default=str)}\n```")
        if layer.warnings:
            out.append("\n### Warnings\n")
            for w in layer.warnings:
                out.append(f"- ⚠ {w}")
        out.append("")
    if report.next_steps:
        out.append("## Next steps\n")
        for step in report.next_steps:
            out.append(f"- {step}")
    return "\n".join(out)


def main() -> int:
    args = parse_args()
    path = Path(args.path).resolve()
    if not path.exists():
        print(json.dumps({"error": "file not found", "path": str(path)}), file=sys.stderr)
        return 1
    format_name, driver = detect_format(path)
    if format_name == "Unknown":
        print(json.dumps({"error": "unsupported format", "path": str(path)}), file=sys.stderr)
        return 1
    report = InspectionReport(
        path=str(path),
        size_bytes=path.stat().st_size if path.is_file() else _dir_size(path),
        format=format_name,
        driver=driver,
        environment=probe_environment(),
    )
    try:
        if driver == "__ezdxf__":
            report.layers = inspect_dxf(path, args.features_sample)
        elif driver == "__libredwg__":
            report.layers = inspect_dwg(path, args.features_sample)
        else:
            report.layers = inspect_fiona(path, driver, args.layer, args.features_sample)
    except ImportError as exc:
        print(json.dumps({"error": f"missing dependency: {exc}"}), file=sys.stderr)
        return 3
    except Exception as exc:
        print(json.dumps({"error": "parse failure", "detail": str(exc)}), file=sys.stderr)
        return 2

    report.next_steps = build_next_steps(report)

    if args.json:
        print(json.dumps(asdict(report), indent=2, default=str))
    else:
        print(render_markdown(report))
    return 0


def _dir_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


if __name__ == "__main__":
    sys.exit(main())

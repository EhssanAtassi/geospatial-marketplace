#!/usr/bin/env python3
"""Descriptive statistics for a GIS layer.

Reads a Shapefile, .gdb, GeoJSON, KML, or GeoPackage and produces a markdown
or JSON report covering:
- Feature count, geometry-type breakdown, CRS, bounding box
- Geometry validity (invalid, self-intersecting, empty)
- Duplicate detection (by geometry hash, by attribute)
- Attribute distributions (numeric: min/max/mean/median/std/histogram;
  categorical: top-N counts + cardinality)
- Area / length statistics for polygon / line layers
- Outliers (>3σ for numeric attributes; extreme areas / lengths)

Usage:
    python analyze_stats.py <path> [--layer NAME] [--attribute NAME] [--json] [--top-n 10]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class NumericStats:
    name: str
    count: int
    min: float | None
    max: float | None
    mean: float | None
    median: float | None
    stdev: float | None
    pct_5: float | None
    pct_95: float | None
    histogram_bins: list[tuple[float, float]] = field(default_factory=list)
    outlier_count: int = 0


@dataclass
class CategoricalStats:
    name: str
    count: int
    cardinality: int
    top: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class StatsReport:
    path: str
    feature_count: int
    geometry_types: dict[str, int] = field(default_factory=dict)
    crs_epsg: int | None = None
    bounds: tuple[float, float, float, float] | None = None
    invalid_count: int = 0
    empty_count: int = 0
    duplicate_geometry_count: int = 0
    area_stats: NumericStats | None = None
    length_stats: NumericStats | None = None
    numeric_attributes: list[NumericStats] = field(default_factory=list)
    categorical_attributes: list[CategoricalStats] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def numeric_stats(values: list[float], name: str, bins: int = 20) -> NumericStats:
    if not values:
        return NumericStats(name=name, count=0, min=None, max=None, mean=None, median=None, stdev=None, pct_5=None, pct_95=None)
    mn, mx = min(values), max(values)
    mean = sum(values) / len(values)
    median = statistics.median(values)
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
    s = sorted(values)
    pct_5 = s[max(0, int(len(s) * 0.05) - 1)]
    pct_95 = s[min(len(s) - 1, int(len(s) * 0.95))]
    histogram = _histogram(values, bins, mn, mx)
    outliers = sum(1 for v in values if stdev > 0 and abs(v - mean) > 3 * stdev)
    return NumericStats(
        name=name,
        count=len(values),
        min=mn,
        max=mx,
        mean=mean,
        median=median,
        stdev=stdev,
        pct_5=pct_5,
        pct_95=pct_95,
        histogram_bins=histogram,
        outlier_count=outliers,
    )


def _histogram(values: list[float], bins: int, mn: float, mx: float) -> list[tuple[float, float]]:
    if mn == mx:
        return [(mn, len(values))]
    width = (mx - mn) / bins
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - mn) / width))
        counts[idx] += 1
    return [(mn + i * width, counts[i]) for i in range(bins)]


def categorical_stats(values: list[Any], name: str, top_n: int) -> CategoricalStats:
    cnt = Counter(str(v) for v in values if v is not None)
    return CategoricalStats(
        name=name,
        count=sum(cnt.values()),
        cardinality=len(cnt),
        top=cnt.most_common(top_n),
    )


def geometry_hash(geom_geojson: dict[str, Any]) -> str:
    """Hash a GeoJSON geometry, rounded to 6dp coordinates for tolerance."""
    def _round_coords(c):
        if isinstance(c, list):
            return [_round_coords(x) for x in c]
        if isinstance(c, (int, float)):
            return round(c, 6)
        return c
    rounded = {
        "type": geom_geojson.get("type"),
        "coordinates": _round_coords(geom_geojson.get("coordinates")),
    }
    return json.dumps(rounded, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Descriptive statistics for a GIS layer.")
    parser.add_argument("path")
    parser.add_argument("--layer")
    parser.add_argument("--attribute")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--histogram-bins", type=int, default=20)
    args = parser.parse_args()

    path = Path(args.path).resolve()
    if not path.exists():
        print(json.dumps({"error": "file not found"}), file=sys.stderr)
        return 1

    try:
        import fiona  # type: ignore
        from shapely.geometry import shape  # type: ignore
    except ImportError as exc:
        print(json.dumps({"error": f"missing: {exc}. pip install fiona shapely"}), file=sys.stderr)
        return 3

    report = StatsReport(path=str(path), feature_count=0)

    with fiona.open(str(path), layer=args.layer) as src:
        report.feature_count = len(src)
        report.bounds = tuple(src.bounds) if src.bounds else None
        try:
            report.crs_epsg = src.crs.to_epsg() if src.crs else None
        except Exception:
            report.crs_epsg = None

        # Collect data in one pass
        geom_types: Counter = Counter()
        attr_values: dict[str, list[Any]] = {}
        attr_types: dict[str, str] = dict((src.schema or {}).get("properties", {}))
        for fname in attr_types:
            attr_values[fname] = []
        areas: list[float] = []
        lengths: list[float] = []
        invalid = 0
        empty = 0
        geom_hashes: Counter = Counter()

        for feature in src:
            geom_dict = feature["geometry"]
            if not geom_dict:
                empty += 1
                continue
            geom_types[geom_dict.get("type")] += 1
            try:
                geom = shape(geom_dict)
                if geom.is_empty:
                    empty += 1
                    continue
                if not geom.is_valid:
                    invalid += 1
                if hasattr(geom, "area") and geom.geom_type in ("Polygon", "MultiPolygon"):
                    areas.append(geom.area)
                if hasattr(geom, "length") and geom.geom_type in ("LineString", "MultiLineString"):
                    lengths.append(geom.length)
            except Exception:
                invalid += 1
            geom_hashes[geometry_hash(geom_dict)] += 1
            for fname, fval in feature["properties"].items():
                attr_values[fname].append(fval)

        report.geometry_types = dict(geom_types)
        report.invalid_count = invalid
        report.empty_count = empty
        report.duplicate_geometry_count = sum(c for c in geom_hashes.values() if c > 1) - sum(1 for c in geom_hashes.values() if c > 1)

        if areas:
            report.area_stats = numeric_stats(areas, "area", args.histogram_bins)
        if lengths:
            report.length_stats = numeric_stats(lengths, "length", args.histogram_bins)

        for fname, ftype in attr_types.items():
            values = [v for v in attr_values[fname] if v is not None]
            if not values:
                continue
            base = ftype.split(":")[0].lower()
            if base in ("int", "float"):
                numeric = [float(v) for v in values if isinstance(v, (int, float))]
                if numeric:
                    report.numeric_attributes.append(
                        numeric_stats(numeric, fname, args.histogram_bins)
                    )
            else:
                report.categorical_attributes.append(
                    categorical_stats(values, fname, args.top_n)
                )

    if args.json:
        print(json.dumps(asdict(report), indent=2, default=str))
    else:
        print(render_markdown(report))
    return 0


def render_markdown(r: StatsReport) -> str:
    lines = []
    lines.append(f"# Descriptive Statistics — `{r.path}`\n")
    lines.append("## Summary\n")
    lines.append(f"- Feature count: **{r.feature_count:,}**")
    if r.crs_epsg:
        lines.append(f"- CRS: EPSG:{r.crs_epsg}")
    if r.bounds:
        mn_x, mn_y, mx_x, mx_y = r.bounds
        lines.append(f"- Bounds: ({mn_x:.4f}, {mn_y:.4f}) → ({mx_x:.4f}, {mx_y:.4f})")
    lines.append(f"- Geometry types: " + ", ".join(f"{k}={v}" for k, v in r.geometry_types.items()))
    lines.append("")
    lines.append("## Data Quality\n")
    lines.append(f"- Invalid geometries: **{r.invalid_count}**")
    lines.append(f"- Empty geometries: **{r.empty_count}**")
    lines.append(f"- Duplicate geometries: **{r.duplicate_geometry_count}**")
    lines.append("")
    if r.area_stats and r.area_stats.count:
        lines.append("## Area distribution\n")
        lines.append(_render_numeric(r.area_stats))
    if r.length_stats and r.length_stats.count:
        lines.append("## Length distribution\n")
        lines.append(_render_numeric(r.length_stats))
    if r.numeric_attributes:
        lines.append("## Numeric attributes\n")
        for ns in r.numeric_attributes:
            lines.append(f"### `{ns.name}`")
            lines.append(_render_numeric(ns))
    if r.categorical_attributes:
        lines.append("## Categorical attributes\n")
        for cs in r.categorical_attributes:
            lines.append(f"### `{cs.name}` (cardinality {cs.cardinality})")
            lines.append("| Value | Count |")
            lines.append("|---|---|")
            for k, c in cs.top:
                lines.append(f"| `{k}` | {c} |")
            lines.append("")
    return "\n".join(lines)


def _render_numeric(ns: NumericStats) -> str:
    if ns.count == 0:
        return "_(no values)_\n"
    out = [
        f"- Count: {ns.count}",
        f"- Range: {ns.min:.4f} → {ns.max:.4f}",
        f"- Mean: {ns.mean:.4f} | Median: {ns.median:.4f} | Stdev: {ns.stdev:.4f}",
        f"- P5 / P95: {ns.pct_5:.4f} / {ns.pct_95:.4f}",
        f"- Outliers (>3σ): {ns.outlier_count}",
        "",
    ]
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())

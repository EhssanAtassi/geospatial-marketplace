#!/usr/bin/env python3
"""Spatial pattern analysis for a point GIS layer.

Runs DBSCAN clustering and nearest-neighbor analysis (Clark-Evans ratio)
on a point layer. Reprojects to local UTM for accurate distance computations.

Usage:
    python analyze_patterns.py <points.shp> [--eps 0.5] [--min-samples 5]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class ClusterSummary:
    cluster_id: int
    point_count: int
    centroid_lng: float
    centroid_lat: float
    convex_hull_area_sqkm: float


@dataclass
class PatternReport:
    path: str
    point_count: int
    crs_epsg: int | None
    utm_zone: str
    clusters: list[ClusterSummary] = field(default_factory=list)
    noise_count: int = 0
    nn_mean_m: float = 0.0
    nn_median_m: float = 0.0
    nn_std_m: float = 0.0
    clark_evans_r: float = 0.0
    interpretation: str = ""
    warnings: list[str] = field(default_factory=list)


def utm_zone_for(lng: float, lat: float) -> tuple[int, str]:
    """Return (epsg_code, label) for the UTM zone covering the given lng/lat."""
    zone = int((lng + 180) / 6) + 1
    hemisphere = "N" if lat >= 0 else "S"
    base = 32600 if hemisphere == "N" else 32700
    return base + zone, f"UTM Zone {zone}{hemisphere}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Spatial pattern analysis on a point layer.")
    parser.add_argument("path")
    parser.add_argument("--eps", type=float, default=0.5, help="DBSCAN eps in km (default 0.5)")
    parser.add_argument("--min-samples", type=int, default=5, help="DBSCAN min_samples (default 5)")
    parser.add_argument("--out-file", help="Output GeoJSON with cluster labels")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    path = Path(args.path).resolve()
    if not path.exists():
        print(json.dumps({"error": "file not found"}), file=sys.stderr)
        return 1

    try:
        import fiona  # type: ignore
        import numpy as np  # type: ignore
        from pyproj import Transformer  # type: ignore
        from shapely.geometry import Point, shape, mapping  # type: ignore
        from sklearn.cluster import DBSCAN  # type: ignore
        from sklearn.neighbors import NearestNeighbors  # type: ignore
    except ImportError as exc:
        print(json.dumps({"error": f"missing: {exc}. pip install fiona shapely pyproj scikit-learn numpy"}), file=sys.stderr)
        return 3

    # Read points
    points_lnglat: list[tuple[float, float]] = []
    props_per_point: list[dict[str, Any]] = []
    with fiona.open(str(path)) as src:
        crs_epsg = src.crs.to_epsg() if src.crs else None
        for feature in src:
            geom_dict = feature["geometry"]
            if not geom_dict or geom_dict.get("type") != "Point":
                continue
            coords = geom_dict["coordinates"]
            points_lnglat.append((float(coords[0]), float(coords[1])))
            props_per_point.append(dict(feature["properties"]))

    if not points_lnglat:
        print(json.dumps({"error": "no point features found"}), file=sys.stderr)
        return 1

    # Reproject to local UTM for accurate distance math
    centroid_lng = sum(p[0] for p in points_lnglat) / len(points_lnglat)
    centroid_lat = sum(p[1] for p in points_lnglat) / len(points_lnglat)
    utm_epsg, utm_label = utm_zone_for(centroid_lng, centroid_lat)
    source_crs = f"EPSG:{crs_epsg}" if crs_epsg else "EPSG:4326"
    transformer = Transformer.from_crs(source_crs, f"EPSG:{utm_epsg}", always_xy=True)
    utm_points = np.array([transformer.transform(lng, lat) for lng, lat in points_lnglat])

    # DBSCAN
    eps_m = args.eps * 1000
    db = DBSCAN(eps=eps_m, min_samples=args.min_samples).fit(utm_points)
    labels = db.labels_
    unique_labels = sorted(set(labels))

    # Build cluster summaries
    inverse_transformer = Transformer.from_crs(f"EPSG:{utm_epsg}", "EPSG:4326", always_xy=True)
    clusters: list[ClusterSummary] = []
    noise_count = int(np.sum(labels == -1))
    for cluster_id in unique_labels:
        if cluster_id == -1:
            continue
        idx = np.where(labels == cluster_id)[0]
        cluster_pts = utm_points[idx]
        cx_m, cy_m = cluster_pts.mean(axis=0)
        cx_lng, cy_lat = inverse_transformer.transform(cx_m, cy_m)
        # Convex-hull area
        if len(cluster_pts) >= 3:
            from shapely.geometry import MultiPoint
            hull = MultiPoint([(x, y) for x, y in cluster_pts]).convex_hull
            area_sqkm = hull.area / 1_000_000  # m² → km²
        else:
            area_sqkm = 0.0
        clusters.append(
            ClusterSummary(
                cluster_id=int(cluster_id),
                point_count=int(len(idx)),
                centroid_lng=float(cx_lng),
                centroid_lat=float(cy_lat),
                convex_hull_area_sqkm=float(area_sqkm),
            )
        )

    # Nearest-neighbor analysis
    nn = NearestNeighbors(n_neighbors=2).fit(utm_points)
    distances, _ = nn.kneighbors(utm_points)
    nn_distances = distances[:, 1]  # 0 is the point itself
    nn_mean = float(np.mean(nn_distances))
    nn_median = float(np.median(nn_distances))
    nn_std = float(np.std(nn_distances))

    # Clark-Evans ratio: R = mean_observed_nn / expected_nn_for_random
    # Expected: 0.5 / sqrt(density)
    if len(utm_points) >= 2:
        bbox = utm_points.min(axis=0), utm_points.max(axis=0)
        area_m2 = (bbox[1][0] - bbox[0][0]) * (bbox[1][1] - bbox[0][1])
        density = len(utm_points) / area_m2 if area_m2 > 0 else 0
        expected_nn = 0.5 / math.sqrt(density) if density > 0 else 0
        ce_r = nn_mean / expected_nn if expected_nn > 0 else 0.0
    else:
        ce_r = 0.0

    if ce_r < 0.7:
        interpretation = "Strongly clustered (R << 1)."
    elif ce_r < 0.95:
        interpretation = "Moderately clustered."
    elif ce_r < 1.05:
        interpretation = "Random (Poisson-like spatial distribution)."
    elif ce_r < 1.3:
        interpretation = "Moderately dispersed."
    else:
        interpretation = "Strongly dispersed / regular grid-like."

    report = PatternReport(
        path=str(path),
        point_count=len(points_lnglat),
        crs_epsg=crs_epsg,
        utm_zone=utm_label,
        clusters=clusters,
        noise_count=noise_count,
        nn_mean_m=nn_mean,
        nn_median_m=nn_median,
        nn_std_m=nn_std,
        clark_evans_r=ce_r,
        interpretation=interpretation,
    )

    # Optional output GeoJSON with labels
    if args.out_file:
        features = []
        for (lng, lat), props, label in zip(points_lnglat, props_per_point, labels):
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lng, lat]},
                    "properties": {**props, "cluster_id": int(label)},
                }
            )
        fc = {"type": "FeatureCollection", "features": features}
        Path(args.out_file).write_text(json.dumps(fc))
        report.warnings.append(f"Labeled GeoJSON written to {args.out_file}")

    if args.json:
        print(json.dumps(asdict(report), indent=2, default=str))
    else:
        print(render_markdown(report))
    return 0


def render_markdown(r: PatternReport) -> str:
    lines = []
    lines.append(f"# Spatial Pattern Analysis — `{r.path}`\n")
    lines.append("## Summary\n")
    lines.append(f"- Points analyzed: **{r.point_count:,}**")
    lines.append(f"- Source CRS: EPSG:{r.crs_epsg or '(unknown)'}")
    lines.append(f"- Analysis CRS: {r.utm_zone}")
    lines.append("")
    lines.append("## Nearest-Neighbor\n")
    lines.append(f"- Mean: {r.nn_mean_m:.1f} m")
    lines.append(f"- Median: {r.nn_median_m:.1f} m")
    lines.append(f"- Stdev: {r.nn_std_m:.1f} m")
    lines.append(f"- **Clark-Evans R = {r.clark_evans_r:.3f}** — {r.interpretation}")
    lines.append("")
    lines.append("## DBSCAN Clusters\n")
    lines.append(f"- Clusters found: **{len(r.clusters)}**")
    lines.append(f"- Noise points: **{r.noise_count}** ({r.noise_count / max(r.point_count, 1) * 100:.1f}%)")
    if r.clusters:
        lines.append("")
        lines.append("| Cluster | Points | Centroid (lng, lat) | Hull area (km²) |")
        lines.append("|---|---|---|---|")
        for c in r.clusters:
            lines.append(
                f"| #{c.cluster_id} | {c.point_count} | ({c.centroid_lng:.4f}, {c.centroid_lat:.4f}) | {c.convex_hull_area_sqkm:.3f} |"
            )
    if r.warnings:
        lines.append("\n## Warnings\n")
        for w in r.warnings:
            lines.append(f"- {w}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())

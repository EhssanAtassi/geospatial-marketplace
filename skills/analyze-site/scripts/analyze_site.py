#!/usr/bin/env python3
"""Site suitability analyzer.

Reads a YAML ruleset for a given purpose (airport / residential / commercial /
public-facility / <custom>) plus a candidate location (point or polygon), then
scores each criterion against the available data sources.

Data sources:
- User-supplied GIS layers (via --data-dir): Shapefile / .gdb / GeoJSON.
- OSM via Overpass API (when --fetch-osm).
- SRTM 30m DEM via OpenTopography (when --fetch-dem).
- Natural Earth pre-downloaded layers (cached in ./.gis-to-db-cache/).

Usage:
    python analyze_site.py --location "lng,lat" --purpose airport
    python analyze_site.py --area parcel.geojson --purpose residential --data-dir ./my-layers --fetch-osm --fetch-dem

Exit codes:
    0  success — markdown report on stdout
    1  user error (bad args, location, ruleset not found)
    2  internal error (parse failure)
    3  missing dependency
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score a candidate site for a purpose.")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--location", help='Candidate location "lng,lat" (degrees)')
    src.add_argument("--area", help="Path to GeoJSON file containing candidate polygon")
    parser.add_argument(
        "--purpose",
        required=True,
        help="Built-in: airport|residential|commercial|public-facility, or custom ruleset name",
    )
    parser.add_argument(
        "--data-dir",
        help="Directory containing user-supplied GIS layers (Shapefile/.gdb/GeoJSON)",
    )
    parser.add_argument(
        "--ruleset-dir",
        help="Override search path for ruleset YAML (default: plugin's assets/rulesets/)",
    )
    parser.add_argument("--fetch-osm", action="store_true", help="Fetch missing layers from OSM")
    parser.add_argument("--fetch-dem", action="store_true", help="Fetch SRTM DEM from OpenTopography")
    parser.add_argument("--no-cache", action="store_true", help="Disable on-disk cache")
    parser.add_argument(
        "--cache-dir", default="./.gis-to-db-cache", help="Cache directory path"
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class CriterionScore:
    name: str
    weight: float
    score: float
    why: str
    raw_value: Any = None
    description: str = ""


@dataclass
class SiteReport:
    purpose: str
    location_label: str
    overall_score: float
    verdict: str
    criteria: list[CriterionScore] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ruleset loading
# ---------------------------------------------------------------------------


def _builtin_ruleset_dir() -> Path:
    """Resolve the plugin's built-in rulesets dir relative to this script."""
    return Path(__file__).resolve().parent.parent.parent.parent / "assets" / "rulesets"


def _user_ruleset_dirs() -> list[Path]:
    return [Path.home() / ".claude" / "gis-to-db" / "rulesets"]


def load_ruleset(purpose: str, override_dir: str | None) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "PyYAML required. Install with: pip install pyyaml"
        ) from exc
    search_dirs: list[Path] = []
    if override_dir:
        search_dirs.append(Path(override_dir))
    search_dirs.append(_builtin_ruleset_dir())
    search_dirs.extend(_user_ruleset_dirs())
    for d in search_dirs:
        candidate = d / f"{purpose}.yaml"
        if candidate.exists():
            return yaml.safe_load(candidate.read_text())
    raise FileNotFoundError(
        f"Ruleset '{purpose}.yaml' not found. Looked in: "
        + ", ".join(str(d) for d in search_dirs)
    )


# ---------------------------------------------------------------------------
# Location handling
# ---------------------------------------------------------------------------


def resolve_candidate(args: argparse.Namespace) -> tuple[Any, str]:
    """Return (shapely_geom_in_4326, label_for_report)."""
    try:
        from shapely.geometry import Point, shape  # type: ignore
    except ImportError as exc:
        raise SystemExit("shapely required. pip install shapely") from exc

    if args.location:
        try:
            lng_str, lat_str = args.location.split(",")
            lng, lat = float(lng_str.strip()), float(lat_str.strip())
        except ValueError as exc:
            raise SystemExit(f"--location must be 'lng,lat' decimal degrees: {exc}")
        if not (-180 <= lng <= 180) or not (-90 <= lat <= 90):
            raise SystemExit(f"--location {args.location!r} out of WGS84 range")
        return Point(lng, lat), f"({lng:.4f}, {lat:.4f})"

    # --area path: read GeoJSON
    area_path = Path(args.area)
    if not area_path.exists():
        raise SystemExit(f"--area file not found: {area_path}")
    fc = json.loads(area_path.read_text())
    if fc.get("type") == "FeatureCollection":
        if not fc.get("features"):
            raise SystemExit("FeatureCollection has no features")
        geom_dict = fc["features"][0]["geometry"]
    elif fc.get("type") == "Feature":
        geom_dict = fc["geometry"]
    elif fc.get("type") in ("Polygon", "MultiPolygon", "Point", "LineString"):
        geom_dict = fc
    else:
        raise SystemExit(f"Unrecognized GeoJSON type: {fc.get('type')}")
    return shape(geom_dict), f"area from {area_path.name}"


# ---------------------------------------------------------------------------
# Scoring curves
# ---------------------------------------------------------------------------


def score_linear_decreasing(value: float, ideal: float, acceptable: float, unacceptable: float) -> float:
    if value <= ideal:
        return 100.0
    if value >= unacceptable:
        return 0.0
    if value <= acceptable:
        # Interpolate ideal..acceptable → 100..70
        t = (value - ideal) / max(acceptable - ideal, 1e-9)
        return 100 - 30 * t
    # acceptable..unacceptable → 70..0
    t = (value - acceptable) / max(unacceptable - acceptable, 1e-9)
    return 70 - 70 * t


def score_linear_increasing(value: float, unacceptable: float, acceptable: float, ideal: float) -> float:
    if value <= unacceptable:
        return 0.0
    if value >= ideal:
        return 100.0
    if value < acceptable:
        t = (value - unacceptable) / max(acceptable - unacceptable, 1e-9)
        return 70 * t
    t = (value - acceptable) / max(ideal - acceptable, 1e-9)
    return 70 + 30 * t


def score_bell(value: float, min_v: float, ideal: float, max_v: float) -> float:
    """Score 100 at ideal, 0 at min/max, linear taper on each side."""
    if value <= min_v or value >= max_v:
        return 0.0
    if value < ideal:
        t = (value - min_v) / max(ideal - min_v, 1e-9)
        return 100 * t
    t = (max_v - value) / max(max_v - ideal, 1e-9)
    return 100 * t


# ---------------------------------------------------------------------------
# Criterion evaluators
# ---------------------------------------------------------------------------


def evaluate_criterion(
    criterion: dict[str, Any],
    candidate_geom: Any,
    layers: dict[str, Any],
    dem: Any,
) -> CriterionScore:
    ctype = criterion.get("type")
    name = criterion["name"]
    weight = float(criterion.get("weight", 1))
    description = criterion.get("description", "")

    if ctype == "distance_to_layer":
        return _eval_distance(criterion, candidate_geom, layers, name, weight, description)
    if ctype == "overlap_with_layer":
        return _eval_overlap(criterion, candidate_geom, layers, name, weight, description)
    if ctype == "terrain_stat":
        return _eval_terrain(criterion, candidate_geom, dem, name, weight, description)
    if ctype == "density_count":
        return _eval_density(criterion, candidate_geom, layers, name, weight, description)
    return CriterionScore(
        name=name,
        weight=weight,
        score=0,
        why=f"Unsupported criterion type '{ctype}'.",
        description=description,
    )


def _eval_distance(
    criterion: dict[str, Any],
    candidate_geom: Any,
    layers: dict[str, Any],
    name: str,
    weight: float,
    description: str,
) -> CriterionScore:
    layer_key = criterion["layer"]
    units = criterion.get("units", "km")
    layer_df = layers.get(layer_key)
    if layer_df is None:
        return CriterionScore(
            name=name,
            weight=weight,
            score=50,
            why=f"Layer '{layer_key}' not available — neutral 50/100 (run with --fetch-osm or supply via --data-dir).",
            description=description,
        )
    # Compute geodesic distance to nearest feature
    try:
        from shapely.ops import nearest_points  # type: ignore
        from pyproj import Geod  # type: ignore
    except ImportError as exc:
        return CriterionScore(name, weight, 0, f"Missing dep: {exc}", description=description)
    geod = Geod(ellps="WGS84")
    min_dist_m = float("inf")
    for geom in _layer_geoms(layer_df):
        p1, p2 = nearest_points(candidate_geom, geom)
        _, _, dist = geod.inv(p1.x, p1.y, p2.x, p2.y)
        if dist < min_dist_m:
            min_dist_m = dist
    dist_value = min_dist_m / 1000 if units == "km" else min_dist_m

    bounds = criterion.get("bounds", {})
    curve = criterion.get("score_curve", "linear_decreasing")
    if curve == "linear_decreasing":
        score = score_linear_decreasing(
            dist_value,
            bounds.get("ideal", 0),
            bounds.get("acceptable", 10),
            bounds.get("unacceptable", 50),
        )
    elif curve == "linear_increasing":
        score = score_linear_increasing(
            dist_value,
            bounds.get("unacceptable", 0),
            bounds.get("acceptable", 30),
            bounds.get("ideal", 80),
        )
    elif curve == "bell":
        score = score_bell(
            dist_value,
            bounds.get("min", 0),
            bounds.get("ideal", 30),
            bounds.get("max", 100),
        )
    else:
        score = 50

    why = f"{dist_value:.2f} {units} to nearest matching feature ({layer_key})."
    return CriterionScore(
        name=name,
        weight=weight,
        score=round(score, 1),
        why=why,
        raw_value=dist_value,
        description=description,
    )


def _eval_overlap(
    criterion: dict[str, Any],
    candidate_geom: Any,
    layers: dict[str, Any],
    name: str,
    weight: float,
    description: str,
) -> CriterionScore:
    layer_key = criterion["layer"]
    score_map = criterion.get("score", {"no_overlap": 100, "partial_overlap": 30, "full_overlap": 0})
    layer_df = layers.get(layer_key)
    if layer_df is None:
        return CriterionScore(
            name=name,
            weight=weight,
            score=50,
            why=f"Layer '{layer_key}' not available — neutral 50/100.",
            description=description,
        )
    overlap_areas = []
    for geom in _layer_geoms(layer_df):
        if not candidate_geom.intersects(geom):
            continue
        if hasattr(candidate_geom, "area") and candidate_geom.area > 0:
            try:
                overlap = candidate_geom.intersection(geom)
                overlap_areas.append(overlap.area / candidate_geom.area)
            except Exception:
                overlap_areas.append(1.0)
        else:
            overlap_areas.append(1.0)
    if not overlap_areas:
        return CriterionScore(
            name=name,
            weight=weight,
            score=score_map.get("no_overlap", 100),
            why=f"No overlap with {layer_key}.",
            description=description,
        )
    max_overlap = max(overlap_areas)
    if max_overlap >= 0.95:
        s = score_map.get("full_overlap", 0)
        why = f"Full overlap with {layer_key} ({max_overlap:.0%})."
    else:
        s = score_map.get("partial_overlap", 30)
        why = f"Partial overlap with {layer_key} ({max_overlap:.0%})."
    return CriterionScore(name, weight, s, why, raw_value=max_overlap, description=description)


def _eval_terrain(
    criterion: dict[str, Any],
    candidate_geom: Any,
    dem: Any,
    name: str,
    weight: float,
    description: str,
) -> CriterionScore:
    stat = criterion.get("stat")
    if dem is None:
        return CriterionScore(
            name=name,
            weight=weight,
            score=50,
            why=f"DEM not available — neutral 50/100 (run with --fetch-dem).",
            description=description,
        )
    if stat == "elevation_meters":
        # Sample the DEM at the centroid
        c = candidate_geom.centroid
        try:
            elevation = float(dem.sample([(c.x, c.y)]).__next__()[0])
        except Exception as exc:
            return CriterionScore(name, weight, 50, f"DEM sample failed: {exc}", description=description)
        raw = elevation
        why = f"Elevation {elevation:.0f}m at centroid."
    elif stat in ("max_slope_degrees", "average_slope_degrees"):
        # Approximate: not implemented in v0.1; return neutral with a warning
        return CriterionScore(
            name=name,
            weight=weight,
            score=50,
            why=f"Slope analysis not implemented in v0.1 — neutral 50/100. (Coming in v0.2 via numpy gradient on DEM.)",
            description=description,
        )
    elif stat == "contiguous_flat_area_hectares":
        return CriterionScore(
            name=name,
            weight=weight,
            score=50,
            why=f"Flat-area analysis not implemented in v0.1 — neutral 50/100. (Coming in v0.2.)",
            description=description,
        )
    else:
        return CriterionScore(name, weight, 50, f"Unknown terrain stat '{stat}'.", description=description)

    bounds = criterion.get("bounds", {})
    curve = criterion.get("score_curve", "linear_increasing")
    if curve == "linear_increasing":
        score = score_linear_increasing(
            raw, bounds.get("unacceptable", 0), bounds.get("acceptable", 100), bounds.get("ideal", 500)
        )
    elif curve == "linear_decreasing":
        score = score_linear_decreasing(
            raw, bounds.get("ideal", 0), bounds.get("acceptable", 100), bounds.get("unacceptable", 500)
        )
    else:
        score = 50
    return CriterionScore(name, weight, round(score, 1), why, raw_value=raw, description=description)


def _eval_density(
    criterion: dict[str, Any],
    candidate_geom: Any,
    layers: dict[str, Any],
    name: str,
    weight: float,
    description: str,
) -> CriterionScore:
    layer_key = criterion["layer"]
    radius_km = float(criterion.get("radius_km", 1))
    layer_df = layers.get(layer_key)
    if layer_df is None:
        return CriterionScore(
            name=name,
            weight=weight,
            score=50,
            why=f"Layer '{layer_key}' not available — neutral 50/100.",
            description=description,
        )
    # Approximate radius in degrees (1° ≈ 111km)
    radius_deg = radius_km / 111
    buffer_geom = candidate_geom.buffer(radius_deg)
    count = sum(1 for g in _layer_geoms(layer_df) if buffer_geom.intersects(g))
    bounds = criterion.get("bounds", {})
    curve = criterion.get("score_curve", "linear_increasing")
    if curve == "linear_increasing":
        score = score_linear_increasing(
            count,
            bounds.get("unacceptable", 0),
            bounds.get("acceptable", 100),
            bounds.get("ideal", 1000),
        )
    elif curve == "bell":
        score = score_bell(count, bounds.get("min", 0), bounds.get("ideal", 100), bounds.get("max", 1000))
    else:
        score = 50
    return CriterionScore(
        name=name,
        weight=weight,
        score=round(score, 1),
        why=f"{count} features within {radius_km}km of candidate ({layer_key}).",
        raw_value=count,
        description=description,
    )


def _layer_geoms(layer_df: Any):
    """Iterate Shapely geometries from a layer (list of geoms or GeoDataFrame)."""
    if hasattr(layer_df, "geometry"):
        for g in layer_df.geometry:
            if g is not None:
                yield g
    elif isinstance(layer_df, list):
        yield from layer_df


# ---------------------------------------------------------------------------
# Layer loading (user-supplied + fetch placeholders)
# ---------------------------------------------------------------------------


def load_user_layers(data_dir: str | None) -> dict[str, Any]:
    """Load any user-supplied GIS files. Layer key = filename without extension."""
    if not data_dir:
        return {}
    try:
        import geopandas as gpd  # type: ignore
    except ImportError:
        return {}
    layers: dict[str, Any] = {}
    for p in Path(data_dir).rglob("*"):
        if p.suffix.lower() not in (".shp", ".geojson", ".json", ".gpkg"):
            continue
        try:
            gdf = gpd.read_file(p)
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(4326)
            layers[f"user:{p.stem}"] = gdf
        except Exception:
            pass
    return layers


def fetch_osm(criteria: list[dict[str, Any]], candidate_geom: Any, cache_dir: str) -> dict[str, Any]:
    """Fetch OSM layers via Overpass for each unique osm:* layer key referenced.

    v0.1: placeholder that returns empty; full Overpass implementation in next phase.
    """
    return {}


def fetch_dem(candidate_geom: Any, cache_dir: str) -> Any | None:
    """Fetch SRTM 30m DEM. v0.1: placeholder."""
    return None


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def verdict_label(score: float, thresholds: dict[str, float]) -> str:
    if score >= thresholds.get("recommended", 70):
        return "RECOMMENDED"
    if score >= thresholds.get("conditional", 50):
        return "CONDITIONAL"
    return "NOT RECOMMENDED"


def render_markdown(report: SiteReport) -> str:
    lines = []
    lines.append(f"# Site Suitability — {report.purpose} at {report.location_label}\n")
    lines.append(f"## Verdict: **{report.verdict}** (score: {report.overall_score:.1f} / 100)\n")
    lines.append("## Criteria\n")
    lines.append("| Criterion | Weight | Score | Why |")
    lines.append("|---|---|---|---|")
    for c in report.criteria:
        lines.append(f"| `{c.name}` | {c.weight:.0f}% | {c.score:.1f} | {c.why} |")
    lines.append("")
    if report.recommendations:
        lines.append("## Recommendations\n")
        for r in report.recommendations:
            lines.append(f"- {r}")
        lines.append("")
    if report.warnings:
        lines.append("## Warnings\n")
        for w in report.warnings:
            lines.append(f"- ⚠ {w}")
        lines.append("")
    if report.data_sources:
        lines.append("## Data Sources\n")
        for s in report.data_sources:
            lines.append(f"- {s}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()
    try:
        ruleset = load_ruleset(args.purpose, args.ruleset_dir)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    try:
        candidate_geom, label = resolve_candidate(args)
    except SystemExit as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    layers: dict[str, Any] = {}
    layers.update(load_user_layers(args.data_dir))
    if args.fetch_osm:
        layers.update(fetch_osm(ruleset["criteria"], candidate_geom, args.cache_dir))
    dem = fetch_dem(candidate_geom, args.cache_dir) if args.fetch_dem else None

    report = SiteReport(
        purpose=ruleset.get("name", args.purpose),
        location_label=label,
        overall_score=0,
        verdict="",
    )
    weighted_total = 0.0
    weight_sum = 0.0
    for criterion in ruleset.get("criteria", []):
        cs = evaluate_criterion(criterion, candidate_geom, layers, dem)
        report.criteria.append(cs)
        weighted_total += cs.score * cs.weight
        weight_sum += cs.weight
    overall = weighted_total / max(weight_sum, 1e-9)
    report.overall_score = overall
    report.verdict = verdict_label(overall, ruleset.get("verdict_thresholds", {}))

    # Data source attribution
    if args.data_dir:
        report.data_sources.append(f"User layers: `{args.data_dir}`")
    if args.fetch_osm:
        report.data_sources.append("OpenStreetMap via Overpass API")
    if args.fetch_dem:
        report.data_sources.append("SRTM 30m DEM via OpenTopography")
    # Auto-generate recommendations from lowest-scoring criteria
    weakest = sorted(report.criteria, key=lambda c: c.score)[:3]
    for c in weakest:
        if c.score < 60:
            report.recommendations.append(
                f"Improve **{c.name}** (current {c.score:.0f}/100): {c.description.strip() or 'see criterion details above'}"
            )

    if args.json:
        print(json.dumps(asdict(report), indent=2, default=str))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

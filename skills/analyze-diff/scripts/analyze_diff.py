#!/usr/bin/env python3
"""Compare two GIS layers and report added / removed / changed features.

Usage:
    python analyze_diff.py <old.shp> <new.shp> [--key parcel_id] [--proximity-tolerance 5]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class ChangedFeature:
    key: str
    area_old: float
    area_new: float
    area_delta_pct: float
    centroid_shift_m: float
    attribute_changes: dict[str, tuple[Any, Any]] = field(default_factory=dict)


@dataclass
class DiffReport:
    old_path: str
    new_path: str
    old_count: int
    new_count: int
    added: list[dict[str, Any]] = field(default_factory=list)
    removed: list[dict[str, Any]] = field(default_factory=list)
    changed: list[ChangedFeature] = field(default_factory=list)
    unchanged_count: int = 0
    warnings: list[str] = field(default_factory=list)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff two GIS layers.")
    parser.add_argument("old_path")
    parser.add_argument("new_path")
    parser.add_argument("--key", help="Attribute name to match features by (preferred)")
    parser.add_argument(
        "--proximity-tolerance",
        type=float,
        default=5,
        help="Max centroid distance (m) for proximity matching (default 5)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    old_p = Path(args.old_path).resolve()
    new_p = Path(args.new_path).resolve()
    if not old_p.exists() or not new_p.exists():
        print(json.dumps({"error": "one or both files not found"}), file=sys.stderr)
        return 1

    try:
        import fiona  # type: ignore
        from pyproj import Transformer  # type: ignore
        from shapely.geometry import shape  # type: ignore
        from shapely.ops import transform as shapely_transform  # type: ignore
    except ImportError as exc:
        print(json.dumps({"error": f"missing: {exc}. pip install fiona shapely pyproj"}), file=sys.stderr)
        return 3

    old_features = list(_read_features(str(old_p)))
    new_features = list(_read_features(str(new_p)))
    if not old_features or not new_features:
        print(json.dumps({"error": "one of the inputs is empty"}), file=sys.stderr)
        return 1

    # Check geometry-type compatibility
    old_types = {f["_shape"].geom_type for f in old_features}
    new_types = {f["_shape"].geom_type for f in new_features}
    if old_types != new_types:
        print(
            json.dumps({"error": f"geometry-type mismatch: old={old_types} new={new_types}"}),
            file=sys.stderr,
        )
        return 1

    report = DiffReport(
        old_path=str(old_p),
        new_path=str(new_p),
        old_count=len(old_features),
        new_count=len(new_features),
    )

    # Match
    if args.key:
        report.warnings.append(f"Matching by attribute key `{args.key}`")
        matched_pairs, unmatched_old, unmatched_new = _match_by_key(old_features, new_features, args.key)
    else:
        report.warnings.append(
            f"No --key provided; matching by centroid proximity within {args.proximity_tolerance}m"
        )
        matched_pairs, unmatched_old, unmatched_new = _match_by_proximity(
            old_features, new_features, args.proximity_tolerance
        )

    # Added / removed
    for f in unmatched_new:
        report.added.append({"key": f.get("_key"), "properties": f["properties"]})
    for f in unmatched_old:
        report.removed.append({"key": f.get("_key"), "properties": f["properties"]})

    # Changed analysis
    for old_f, new_f in matched_pairs:
        change = _compare_features(old_f, new_f)
        if change is not None:
            report.changed.append(change)
        else:
            report.unchanged_count += 1

    if args.json:
        print(json.dumps(asdict(report), indent=2, default=str))
    else:
        print(render_markdown(report))
    return 0


def _read_features(path: str):
    import fiona  # type: ignore
    from shapely.geometry import shape  # type: ignore

    with fiona.open(path) as src:
        for feature in src:
            geom_dict = feature["geometry"]
            if not geom_dict:
                continue
            try:
                geom = shape(geom_dict)
            except Exception:
                continue
            yield {
                "_shape": geom,
                "_key": str(feature.get("id", "")),
                "properties": dict(feature["properties"]),
            }


def _match_by_key(old_features, new_features, key: str):
    old_by_key = {f["properties"].get(key): f for f in old_features if f["properties"].get(key) is not None}
    new_by_key = {f["properties"].get(key): f for f in new_features if f["properties"].get(key) is not None}
    matched = []
    for k, of in old_by_key.items():
        of["_key"] = str(k)
        nf = new_by_key.get(k)
        if nf:
            nf["_key"] = str(k)
            matched.append((of, nf))
    matched_keys = {of["_key"] for of, _ in matched}
    unmatched_old = [f for k, f in old_by_key.items() if str(k) not in matched_keys]
    unmatched_new = [f for k, f in new_by_key.items() if str(k) not in matched_keys]
    return matched, unmatched_old, unmatched_new


def _match_by_proximity(old_features, new_features, tolerance_m: float):
    # For simplicity, use degree-tolerance approximated as meters (1° ≈ 111km)
    tolerance_deg = tolerance_m / 111000
    matched = []
    used_new = set()
    for of in old_features:
        oc = of["_shape"].centroid
        best_idx = None
        best_dist = float("inf")
        for i, nf in enumerate(new_features):
            if i in used_new:
                continue
            nc = nf["_shape"].centroid
            dist = oc.distance(nc)
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        if best_idx is not None and best_dist <= tolerance_deg:
            used_new.add(best_idx)
            of["_key"] = f"old#{id(of)}"
            new_features[best_idx]["_key"] = of["_key"]
            matched.append((of, new_features[best_idx]))
    matched_old_ids = {id(of) for of, _ in matched}
    matched_new_ids = {id(nf) for _, nf in matched}
    unmatched_old = [f for f in old_features if id(f) not in matched_old_ids]
    unmatched_new = [f for f in new_features if id(f) not in matched_new_ids]
    return matched, unmatched_old, unmatched_new


def _compare_features(old_f, new_f) -> ChangedFeature | None:
    old_geom = old_f["_shape"]
    new_geom = new_f["_shape"]
    area_old = old_geom.area
    area_new = new_geom.area
    area_pct = ((area_new - area_old) / area_old * 100) if area_old else 0.0
    # Centroid shift in degrees → approximate meters
    c_shift_deg = old_geom.centroid.distance(new_geom.centroid)
    c_shift_m = c_shift_deg * 111000
    attribute_changes: dict[str, tuple[Any, Any]] = {}
    for k, old_v in old_f["properties"].items():
        new_v = new_f["properties"].get(k)
        if old_v != new_v:
            attribute_changes[k] = (old_v, new_v)
    # Unchanged?
    if abs(area_pct) < 0.1 and c_shift_m < 0.5 and not attribute_changes:
        return None
    return ChangedFeature(
        key=old_f.get("_key", ""),
        area_old=area_old,
        area_new=area_new,
        area_delta_pct=area_pct,
        centroid_shift_m=c_shift_m,
        attribute_changes=attribute_changes,
    )


def render_markdown(r: DiffReport) -> str:
    lines = []
    lines.append(f"# GIS Diff — `{r.old_path}` → `{r.new_path}`\n")
    lines.append("## Summary\n")
    lines.append(f"- Old feature count: **{r.old_count:,}**")
    lines.append(f"- New feature count: **{r.new_count:,}**")
    lines.append(f"- Added: **{len(r.added)}**")
    lines.append(f"- Removed: **{len(r.removed)}**")
    lines.append(f"- Changed: **{len(r.changed)}**")
    lines.append(f"- Unchanged: **{r.unchanged_count}**")
    lines.append("")
    if r.added:
        lines.append("## Added\n")
        for f in r.added[:20]:
            lines.append(f"- `{f['key']}` — {dict(list(f['properties'].items())[:5])}")
        if len(r.added) > 20:
            lines.append(f"_(... {len(r.added) - 20} more)_")
        lines.append("")
    if r.removed:
        lines.append("## Removed\n")
        for f in r.removed[:20]:
            lines.append(f"- `{f['key']}` — {dict(list(f['properties'].items())[:5])}")
        if len(r.removed) > 20:
            lines.append(f"_(... {len(r.removed) - 20} more)_")
        lines.append("")
    if r.changed:
        lines.append("## Changed (first 20)\n")
        lines.append("| Key | Area Δ% | Centroid shift (m) | Attribute changes |")
        lines.append("|---|---|---|---|")
        for c in r.changed[:20]:
            attr_str = ", ".join(f"{k}:{old}→{new}" for k, (old, new) in list(c.attribute_changes.items())[:3])
            lines.append(
                f"| `{c.key}` | {c.area_delta_pct:+.2f}% | {c.centroid_shift_m:.2f} | {attr_str or '(none)'} |"
            )
        if len(r.changed) > 20:
            lines.append(f"_(... {len(r.changed) - 20} more)_")
        lines.append("")
    if r.warnings:
        lines.append("## Notes\n")
        for w in r.warnings:
            lines.append(f"- {w}")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())

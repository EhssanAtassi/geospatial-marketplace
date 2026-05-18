#!/usr/bin/env python3
"""Permit / compliance check rule engine.

Scores a proposed project against a jurisdiction's zoning ruleset and emits
a per-rule pass/fail report with citations. Advisory only — final permit
decisions remain with regulatory authorities.

Usage:
    python permit_check.py \
      --area parcel.geojson \
      --proposal proposal.json \
      [--jurisdiction <name>] [--zone <code>] \
      [--ruleset-dir <path>] [--json]

Exit codes:
    0  success — report on stdout (verdict can still be NON-COMPLIANT)
    1  user error (bad input)
    2  internal error
    3  missing dependency
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RuleResult:
    name: str
    rule_type: str
    required: str
    proposed: str
    passed: bool
    citation: str = ""
    detail: str = ""


@dataclass
class PermitReport:
    parcel_id: str
    jurisdiction: str
    zone_code: str
    ruleset_name: str
    ruleset_source: str
    verdict: str
    violations: int
    passes: int
    rules: list[RuleResult] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    run_id: str = ""
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Score a project against a zoning ruleset.")
    p.add_argument("--area", required=True, help="GeoJSON file with parcel(s)")
    p.add_argument("--proposal", required=True, help="JSON file with proposed project parameters")
    p.add_argument("--jurisdiction", help="Override jurisdiction (else from parcel properties)")
    p.add_argument("--zone", help="Override zone code (else from parcel properties)")
    p.add_argument(
        "--ruleset-dir",
        help="Additional search dir for ruleset YAML (in addition to ~/.claude/civic-gis/rulesets and built-in)",
    )
    p.add_argument("--units", choices=["si", "imperial"], default="si")
    p.add_argument("--json", action="store_true")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Ruleset loading
# ---------------------------------------------------------------------------


def _builtin_ruleset_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "rulesets"


def _user_ruleset_dirs() -> list[Path]:
    return [Path.home() / ".claude" / "civic-gis" / "rulesets"]


def load_ruleset(jurisdiction: str, zone: str, override_dir: str | None) -> tuple[dict[str, Any], str]:
    """Return (ruleset_dict, source_path)."""
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise SystemExit("PyYAML required. pip install pyyaml") from exc
    search_dirs: list[Path] = []
    if override_dir:
        search_dirs.append(Path(override_dir))
    search_dirs.extend([d / jurisdiction for d in _user_ruleset_dirs()])
    search_dirs.append(_builtin_ruleset_dir())

    for d in search_dirs:
        candidate = d / f"{zone}.yaml"
        if candidate.exists():
            return yaml.safe_load(candidate.read_text()), str(candidate)
    raise FileNotFoundError(
        f"Ruleset for jurisdiction='{jurisdiction}' zone='{zone}' not found. "
        f"Searched: {', '.join(str(d) for d in search_dirs)}"
    )


# ---------------------------------------------------------------------------
# Derived field computation
# ---------------------------------------------------------------------------


def compute_derived(proposal: dict[str, Any], parcel_area_sqm: float) -> dict[str, Any]:
    """Compute fields that rules may reference but aren't in the proposal."""
    derived = dict(proposal)
    if "footprint_sqm" in proposal and parcel_area_sqm > 0:
        derived["lot_coverage_pct"] = proposal["footprint_sqm"] / parcel_area_sqm * 100
        derived["open_space_pct"] = 100 - derived["lot_coverage_pct"]
    if "gross_floor_area_sqm" in proposal and parcel_area_sqm > 0:
        derived["FAR"] = proposal["gross_floor_area_sqm"] / parcel_area_sqm
    if "gross_floor_area_sqm" in proposal and "avg_unit_size_sqm" not in proposal:
        # Heuristic default — overridden by ruleset's `unit_size_assumption_sqm`
        derived["units"] = math.ceil(proposal["gross_floor_area_sqm"] / 80)
    derived["parcel_area_sqm"] = parcel_area_sqm
    return derived


# ---------------------------------------------------------------------------
# Rule evaluators
# ---------------------------------------------------------------------------


def evaluate_rule(rule: dict[str, Any], values: dict[str, Any]) -> RuleResult:
    rtype = rule.get("type")
    name = rule["name"]
    citation = rule.get("citation", "")

    if rtype == "max":
        return _eval_max(rule, values, name, citation)
    if rtype == "min":
        return _eval_min(rule, values, name, citation)
    if rtype == "range":
        return _eval_range(rule, values, name, citation)
    if rtype == "allowed_values":
        return _eval_allowed(rule, values, name, citation)
    if rtype == "ratio_min":
        return _eval_ratio_min(rule, values, name, citation)
    if rtype == "setback_check":
        return _eval_setback_check(rule, values, name, citation)
    return RuleResult(
        name=name,
        rule_type=rtype or "unknown",
        required=f"unsupported rule type '{rtype}'",
        proposed="",
        passed=False,
        citation=citation,
        detail=f"Rule type '{rtype}' is not implemented in v0.1.",
    )


def _get_value(field_name: str, values: dict[str, Any]) -> Any:
    if field_name not in values:
        return None
    return values[field_name]


def _eval_max(rule, values, name, citation):
    f = rule["field"]
    limit = rule["limit"]
    v = _get_value(f, values)
    if v is None:
        return RuleResult(name, "max", f"≤ {limit}", "MISSING", False, citation, f"Field `{f}` not in proposal.")
    passed = v <= limit
    return RuleResult(name, "max", f"≤ {limit}", str(v), passed, citation)


def _eval_min(rule, values, name, citation):
    f = rule["field"]
    limit = rule["limit"]
    v = _get_value(f, values)
    if v is None:
        return RuleResult(name, "min", f"≥ {limit}", "MISSING", False, citation, f"Field `{f}` not in proposal.")
    passed = v >= limit
    return RuleResult(name, "min", f"≥ {limit}", str(v), passed, citation)


def _eval_range(rule, values, name, citation):
    f = rule["field"]
    mn = rule.get("min")
    mx = rule.get("max")
    v = _get_value(f, values)
    if v is None:
        return RuleResult(name, "range", f"[{mn}, {mx}]", "MISSING", False, citation, f"Field `{f}` not in proposal.")
    passed = (mn is None or v >= mn) and (mx is None or v <= mx)
    return RuleResult(name, "range", f"[{mn}, {mx}]", str(v), passed, citation)


def _eval_allowed(rule, values, name, citation):
    f = rule["field"]
    allowed = rule["allowed"]
    v = _get_value(f, values)
    if v is None:
        return RuleResult(name, "allowed_values", str(allowed), "MISSING", False, citation, f"Field `{f}` not in proposal.")
    passed = v in allowed
    return RuleResult(name, "allowed_values", ", ".join(map(str, allowed)), str(v), passed, citation)


def _eval_ratio_min(rule, values, name, citation):
    f = rule["field"]
    denom_field = rule["denominator"]
    ratio = rule["ratio"]
    num = _get_value(f, values)
    denom = _get_value(denom_field, values)
    if num is None or denom is None:
        return RuleResult(
            name,
            "ratio_min",
            f"≥ {ratio} per {denom_field}",
            "MISSING",
            False,
            citation,
            f"Need both `{f}` and `{denom_field}` in proposal.",
        )
    if denom == 0:
        return RuleResult(name, "ratio_min", f"≥ {ratio} per {denom_field}", "DIV/0", False, citation)
    passed = (num / denom) >= ratio
    actual_ratio = num / denom
    return RuleResult(
        name,
        "ratio_min",
        f"≥ {ratio} per {denom_field} ({denom} × {ratio} = {denom * ratio:.1f})",
        f"{num} ({actual_ratio:.2f} per {denom_field})",
        passed,
        citation,
    )


def _eval_setback_check(rule, values, name, citation):
    fields_map = rule["fields"]
    limits = rule["limits"]
    failures: list[str] = []
    proposed_strs: list[str] = []
    for direction, field_name in fields_map.items():
        v = _get_value(field_name, values)
        limit = limits.get(direction)
        if v is None or limit is None:
            failures.append(f"{direction}=MISSING")
            continue
        if v < limit:
            failures.append(f"{direction}={v} (need ≥ {limit})")
        proposed_strs.append(f"{direction}={v}")
    passed = not failures
    return RuleResult(
        name,
        "setback_check",
        ", ".join(f"{d}≥{l}" for d, l in limits.items()),
        ", ".join(proposed_strs),
        passed,
        citation,
        detail="; ".join(failures) if failures else "",
    )


# ---------------------------------------------------------------------------
# Recommendation generation
# ---------------------------------------------------------------------------


def generate_recommendations(rules: list[RuleResult], values: dict[str, Any], ruleset: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    for r in rules:
        if r.passed:
            continue
        if r.rule_type == "max":
            recs.append(
                f"Reduce `{_find_field(r.name, ruleset)}` to {r.required.split('≤')[-1].strip()} OR apply for variance."
            )
        elif r.rule_type == "min":
            recs.append(
                f"Increase `{_find_field(r.name, ruleset)}` to {r.required.split('≥')[-1].strip()} OR apply for variance."
            )
        elif r.rule_type == "allowed_values":
            recs.append(f"Change `{_find_field(r.name, ruleset)}` to one of: {r.required}.")
        elif r.rule_type == "setback_check":
            recs.append(f"Adjust setbacks: {r.detail}")
        elif r.rule_type == "ratio_min":
            recs.append(f"Increase the count side of `{r.name}` to meet ratio: {r.required}.")
    return recs


def _find_field(rule_name: str, ruleset: dict[str, Any]) -> str:
    for rule in ruleset.get("rules", []):
        if rule.get("name") == rule_name:
            return rule.get("field", rule_name)
    return rule_name


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def render_markdown(report: PermitReport) -> str:
    lines = []
    lines.append(f"# Permit Check — {report.parcel_id} ({report.zone_code}, {report.jurisdiction})\n")
    lines.append(f"**Ruleset:** {report.ruleset_name}  ")
    lines.append(f"**Source:** `{report.ruleset_source}`\n")
    badge = "COMPLIANT" if report.violations == 0 else f"NON-COMPLIANT ({report.violations} violations)"
    lines.append(f"## Verdict: **{badge}**\n")
    lines.append("| Rule | Required | Proposed | Status |")
    lines.append("|---|---|---|---|")
    for r in report.rules:
        status = "✓ PASS" if r.passed else "❌ FAIL"
        lines.append(f"| `{r.name}` | {r.required} | {r.proposed} | {status} |")
        if not r.passed and r.citation:
            lines.append(f"| | _citation:_ {r.citation} | | |")
    if report.recommendations:
        lines.append("\n## Recommendations\n")
        for rec in report.recommendations:
            lines.append(f"- {rec}")
    if report.warnings:
        lines.append("\n## Warnings\n")
        for w in report.warnings:
            lines.append(f"- ⚠ {w}")
    lines.append("\n## Authoritative Note\n")
    lines.append(
        "This check is **advisory**. Final permit decisions require review by the relevant regulatory "
        "authority. Cite this report's run-id when submitting: `" + report.run_id + "`."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()

    try:
        parcel_fc = json.loads(Path(args.area).read_text())
    except Exception as exc:
        print(json.dumps({"error": f"failed to read parcel: {exc}"}), file=sys.stderr)
        return 1

    if parcel_fc.get("type") == "FeatureCollection":
        if not parcel_fc.get("features"):
            print(json.dumps({"error": "empty FeatureCollection"}), file=sys.stderr)
            return 1
        parcel = parcel_fc["features"][0]
    elif parcel_fc.get("type") == "Feature":
        parcel = parcel_fc
    else:
        print(json.dumps({"error": "expected Feature or FeatureCollection"}), file=sys.stderr)
        return 1

    parcel_props = parcel.get("properties", {})
    jurisdiction = args.jurisdiction or parcel_props.get("jurisdiction")
    zone = args.zone or parcel_props.get("zone_code")
    parcel_id = parcel_props.get("parcel_id", "(unknown)")
    parcel_area = parcel_props.get("area_sqm")
    if parcel_area is None:
        # Compute from geometry as fallback (in degrees² — warn)
        print(
            json.dumps({"warning": "parcel.area_sqm not provided; FAR / coverage rules may be inaccurate"}),
            file=sys.stderr,
        )
        parcel_area = 0

    if not jurisdiction or not zone:
        print(
            json.dumps({"error": "jurisdiction and zone are required (via flags or parcel properties)"}),
            file=sys.stderr,
        )
        return 1

    try:
        ruleset, ruleset_path = load_ruleset(jurisdiction, zone, args.ruleset_dir)
    except FileNotFoundError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    try:
        proposal = json.loads(Path(args.proposal).read_text())
    except Exception as exc:
        print(json.dumps({"error": f"failed to read proposal: {exc}"}), file=sys.stderr)
        return 1

    values = compute_derived(proposal, parcel_area or 0)

    rule_results = [evaluate_rule(r, values) for r in ruleset.get("rules", [])]
    violations = sum(1 for r in rule_results if not r.passed)
    passes = sum(1 for r in rule_results if r.passed)
    run_id = (
        "civic-gis-permit-check-"
        + datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
        + "-"
        + parcel_id
    )

    verdict = "COMPLIANT" if violations == 0 else "NON-COMPLIANT"

    report = PermitReport(
        parcel_id=parcel_id,
        jurisdiction=jurisdiction,
        zone_code=zone,
        ruleset_name=ruleset.get("name", zone),
        ruleset_source=ruleset_path,
        verdict=verdict,
        violations=violations,
        passes=passes,
        rules=rule_results,
        recommendations=generate_recommendations(rule_results, values, ruleset),
        run_id=run_id,
    )

    if args.json:
        print(json.dumps(asdict(report), indent=2, default=str))
    else:
        print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

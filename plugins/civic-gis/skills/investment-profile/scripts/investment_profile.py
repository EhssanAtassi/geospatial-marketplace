#!/usr/bin/env python3
"""Investment profile generator for small cities and towns.

Reads user-supplied town data (demographics, infrastructure, land availability)
and produces an investor-ready markdown report. Optionally fetches missing
data from OpenStreetMap and World Bank (v0.1: placeholders that return empty
layers with neutral text).

Usage:
    python investment_profile.py \
      --town "Tartus" \
      --bbox "35.85,34.85,35.95,34.95" \
      --data-dir ./tartus-data \
      [--language en|ar|fr] [--format markdown|json|pdf]
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Stat:
    label: str
    value: Any
    source: str
    as_of: str
    unit: str = ""

    def formatted(self) -> str:
        if self.unit:
            return f"{self.value} {self.unit}"
        return str(self.value)


@dataclass
class ProfileSection:
    title: str
    stats: list[Stat] = field(default_factory=list)
    narrative: str = ""
    missing_data_note: str = ""


@dataclass
class TownProfile:
    town: str
    boundary_source: str
    language: str
    generated_at: str
    at_a_glance: ProfileSection
    demographics: ProfileSection
    infrastructure: ProfileSection
    land: ProfileSection
    economy: ProfileSection
    why_now: ProfileSection
    risks: list[str] = field(default_factory=list)
    comparable_cities: list[dict[str, Any]] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate an investor-ready town profile.")
    p.add_argument("--town", required=True, help="Town/city name")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--bbox", help='Bounding box "minLng,minLat,maxLng,maxLat"')
    src.add_argument("--boundary", help="Path to GeoJSON boundary")
    p.add_argument("--data-dir", help="Directory with user-supplied town data files")
    p.add_argument("--language", default="en", choices=["en", "ar", "fr"])
    p.add_argument("--format", default="markdown", choices=["markdown", "json", "pdf"])
    p.add_argument("--output", help="Output file path (otherwise stdout)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def load_user_data(data_dir: str | None) -> dict[str, Any]:
    """Load any user-supplied data files. Convention: filename = category key."""
    if not data_dir:
        return {}
    out: dict[str, Any] = {}
    for p in Path(data_dir).rglob("*"):
        if p.is_dir():
            continue
        try:
            if p.suffix.lower() == ".json":
                out[p.stem] = json.loads(p.read_text())
            elif p.suffix.lower() == ".csv":
                # Simple CSV load (no pandas dep)
                lines = p.read_text().splitlines()
                if len(lines) < 2:
                    continue
                headers = [h.strip() for h in lines[0].split(",")]
                rows = []
                for line in lines[1:]:
                    if not line.strip():
                        continue
                    vals = [v.strip() for v in line.split(",")]
                    rows.append(dict(zip(headers, vals)))
                out[p.stem] = rows
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def build_demographics(user_data: dict[str, Any]) -> ProfileSection:
    section = ProfileSection(title="People (Demographics)")
    demo = user_data.get("demographics", {})
    if isinstance(demo, list):
        # Assume CSV with rows; pick most-recent
        demo = demo[-1] if demo else {}
    if not demo:
        section.missing_data_note = (
            "No demographics data supplied. Drop a `demographics.json` or `demographics.csv` "
            "into --data-dir, or v0.2 will auto-fetch from World Bank for country-level fallback."
        )
        return section
    # Common fields we look for
    field_map = [
        ("Population", "population", "people"),
        ("Working-age (15-64) %", "working_age_pct", "%"),
        ("Post-secondary education %", "post_secondary_pct", "%"),
        ("Population trend (5y)", "population_5y_change", "%"),
        ("Median household income", "median_income", ""),
        ("Unemployment rate", "unemployment_pct", "%"),
        ("Average wage (monthly)", "average_wage", ""),
    ]
    for label, key, unit in field_map:
        if key in demo:
            section.stats.append(
                Stat(
                    label=label,
                    value=demo[key],
                    source=demo.get("source", "user-supplied"),
                    as_of=str(demo.get("as_of", "(undated)")),
                    unit=unit,
                )
            )
    return section


def build_infrastructure(user_data: dict[str, Any]) -> ProfileSection:
    section = ProfileSection(title="Access (Infrastructure)")
    infra = user_data.get("infrastructure", {})
    if not infra:
        section.missing_data_note = (
            "No infrastructure data supplied. v0.2 will auto-fetch from OpenStreetMap "
            "for road, rail, port distances."
        )
        return section
    fields = [
        ("Distance to highway", "highway_distance_km", "km"),
        ("Distance to nearest port", "port_distance_km", "km"),
        ("Distance to nearest airport", "airport_distance_km", "km"),
        ("Distance to nearest rail station", "rail_distance_km", "km"),
        ("Broadband availability", "broadband_max_mbps", "Mbps"),
        ("Power grid reliability", "power_reliability", ""),
        ("Water grid coverage", "water_coverage_pct", "%"),
        ("Natural gas available", "gas_available", ""),
    ]
    for label, key, unit in fields:
        if key in infra:
            section.stats.append(
                Stat(label=label, value=infra[key], source=infra.get("source", "user-supplied"),
                     as_of=str(infra.get("as_of", "(undated)")), unit=unit)
            )
    return section


def build_land(user_data: dict[str, Any]) -> ProfileSection:
    section = ProfileSection(title="Land Availability")
    land = user_data.get("land", {})
    if not land:
        section.missing_data_note = (
            "No land-availability data supplied. Use `gis-to-db:convert` to ingest "
            "the town's cadastre + zoning layer, then save as `land.json` with "
            "aggregate fields (total ha by zone, average price, etc.)."
        )
        return section
    fields = [
        ("Total developable area", "total_developable_ha", "ha"),
        ("Industrial-zoned land", "industrial_ha", "ha"),
        ("Commercial-zoned land", "commercial_ha", "ha"),
        ("Residential-zoned land", "residential_ha", "ha"),
        ("Average price (industrial)", "industrial_price_per_sqm", "/m²"),
        ("Vacant land near infrastructure", "vacant_serviced_ha", "ha"),
    ]
    for label, key, unit in fields:
        if key in land:
            section.stats.append(
                Stat(label=label, value=land[key], source=land.get("source", "user-supplied"),
                     as_of=str(land.get("as_of", "(undated)")), unit=unit)
            )
    return section


def build_economy(user_data: dict[str, Any]) -> ProfileSection:
    section = ProfileSection(title="Existing Economy")
    econ = user_data.get("economy", {})
    if not econ:
        section.missing_data_note = "No economy data supplied. Add `economy.json` with major employers, industry mix, recent investments."
        return section
    # Most "economy" fields are narrative / lists
    if "major_employers" in econ:
        section.narrative += "**Major employers:** " + ", ".join(
            f"{e.get('name')} ({e.get('sector')}, {e.get('headcount', '?')} employees)"
            for e in econ["major_employers"]
        ) + "\n\n"
    if "top_industries" in econ:
        section.narrative += "**Top industries (by employment):** " + ", ".join(
            f"{i.get('industry')} ({i.get('share_pct')}%)" for i in econ["top_industries"]
        ) + "\n\n"
    if "recent_investments" in econ:
        ri = econ["recent_investments"]
        section.stats.append(
            Stat(
                label="Recent investments (last 5y)",
                value=ri.get("count_5y", "?"),
                source=econ.get("source", "user-supplied"),
                as_of=str(econ.get("as_of", "(undated)")),
            )
        )
        section.stats.append(
            Stat(
                label="Total amount invested (last 5y)",
                value=ri.get("total_5y_usd", "?"),
                source=econ.get("source", "user-supplied"),
                as_of=str(econ.get("as_of", "(undated)")),
                unit="USD",
            )
        )
    return section


def build_why_now(user_data: dict[str, Any]) -> ProfileSection:
    section = ProfileSection(title="Why Now")
    wn = user_data.get("why_now", {})
    if not wn:
        section.missing_data_note = (
            "No 'why_now' data supplied. Add `why_now.json` listing current incentives, "
            "recent infrastructure improvements, competitive advantages, AND known risks."
        )
        return section
    if "incentives" in wn:
        section.narrative += "**Current incentives:**\n"
        for i in wn["incentives"]:
            section.narrative += f"- {i}\n"
        section.narrative += "\n"
    if "recent_improvements" in wn:
        section.narrative += "**Recent improvements:**\n"
        for r in wn["recent_improvements"]:
            section.narrative += f"- {r}\n"
        section.narrative += "\n"
    if "advantages" in wn:
        section.narrative += "**Competitive advantages:**\n"
        for a in wn["advantages"]:
            section.narrative += f"- {a}\n"
    return section


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_markdown(profile: TownProfile) -> str:
    lines: list[str] = []
    lines.append(f"# Investment Profile — {profile.town}\n")
    lines.append(f"_Generated {profile.generated_at} (language: {profile.language})_\n")
    lines.append(f"_Boundary source: {profile.boundary_source}_\n")
    lines.append("---\n")

    # At-a-glance
    lines.append(f"## At-a-Glance\n")
    if profile.at_a_glance.stats:
        for s in profile.at_a_glance.stats:
            lines.append(f"- **{s.label}**: {s.formatted()}  *(source: {s.source}, as of {s.as_of})*")
    if profile.at_a_glance.missing_data_note:
        lines.append(f"_{profile.at_a_glance.missing_data_note}_")
    lines.append("")

    # Each numbered section
    for i, section in enumerate([profile.demographics, profile.infrastructure, profile.land,
                                  profile.economy, profile.why_now], 1):
        lines.append(f"## {i}. {section.title}\n")
        if section.stats:
            lines.append("| Indicator | Value | Source | As-of |")
            lines.append("|---|---|---|---|")
            for s in section.stats:
                lines.append(f"| {s.label} | {s.formatted()} | {s.source} | {s.as_of} |")
            lines.append("")
        if section.narrative:
            lines.append(section.narrative)
        if section.missing_data_note:
            lines.append(f"> ⚠ {section.missing_data_note}\n")

    # Risks — required honesty
    lines.append("## Risks to Flag\n")
    if profile.risks:
        for r in profile.risks:
            lines.append(f"- {r}")
    else:
        lines.append(
            "_No risks listed. Profiles that hide risks lose credibility on first investor contact._  \n"
            "_Add a `risks` array to `why_now.json` listing currency, regulatory, security, infrastructure risks._"
        )
    lines.append("")

    # Comparable cities
    lines.append("## Comparable Cities\n")
    if profile.comparable_cities:
        lines.append("| Town | Distance | Similar attribute | What worked |")
        lines.append("|---|---|---|---|")
        for c in profile.comparable_cities:
            lines.append(
                f"| {c.get('name', '?')} | {c.get('distance_km', '?')} km | "
                f"{c.get('similar_to', '?')} | {c.get('what_worked', '?')} |"
            )
    else:
        lines.append(
            "_v0.2 will auto-suggest comparable cities by matching population band + industry mix + region._  \n"
            "_For now, add a `comparable_cities` array to `economy.json` with manually curated peers._"
        )
    lines.append("")

    # Sources
    lines.append("## Data Sources\n")
    for s in profile.data_sources:
        lines.append(f"- {s}")
    if not profile.data_sources:
        lines.append("- _(none — all data was user-supplied without source attribution)_")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = parse_args()
    user_data = load_user_data(args.data_dir)

    # At-a-glance section: pull headline numbers from sub-sections later
    at_a_glance = ProfileSection(title="At-a-Glance")
    demo = build_demographics(user_data)
    infra = build_infrastructure(user_data)
    land = build_land(user_data)
    econ = build_economy(user_data)
    why_now = build_why_now(user_data)

    # Headline stats from each section
    for source_section, headline_label in [
        (demo, "Population"),
        (land, "Industrial-zoned land"),
        (infra, "Distance to highway"),
    ]:
        for s in source_section.stats:
            if headline_label.lower() in s.label.lower():
                at_a_glance.stats.append(s)
                break

    profile = TownProfile(
        town=args.town,
        boundary_source=(args.bbox or args.boundary or "(not provided)"),
        language=args.language,
        generated_at=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        at_a_glance=at_a_glance,
        demographics=demo,
        infrastructure=infra,
        land=land,
        economy=econ,
        why_now=why_now,
        risks=user_data.get("why_now", {}).get("risks", []),
        comparable_cities=user_data.get("economy", {}).get("comparable_cities", []),
        data_sources=[f"User-supplied: `{args.data_dir}`"] if args.data_dir else [],
    )

    if args.format == "json":
        out = json.dumps(asdict(profile), indent=2, default=str)
    elif args.format == "pdf":
        # v0.1: not implemented — write markdown and instruct user to use pandoc
        md = render_markdown(profile)
        out = (
            md
            + "\n\n---\n_(PDF generation is v0.2. To convert this markdown to PDF manually:_  \n"
            "`pandoc input.md -o output.pdf --pdf-engine=xelatex`)_"
        )
    else:
        out = render_markdown(profile)

    if args.output:
        Path(args.output).write_text(out)
        print(f"Wrote: {args.output}")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

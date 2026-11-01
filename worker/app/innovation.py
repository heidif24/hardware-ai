from __future__ import annotations
import json, re
from pathlib import Path
from typing import Any

def _terms(design: dict[str, Any], notes: str) -> set[str]:
    raw = json.dumps(design, ensure_ascii=False).lower() + " " + notes.lower()
    return set(re.findall(r"[a-z]{3,}", raw))

def _need(terms: set[str], words: set[str]) -> bool:
    return bool(terms & words)

def build_innovation_dossier(root: Path, design: dict[str, Any], selections: dict[str, str], notes: str) -> list[dict[str, Any]]:
    """Create engineering candidates and interface-family contract for the engineering workspace.

    Cost and durability reasoning is applied internally when choosing a primary path.
    Those figures and comparison tables are NOT written into the hand-off package for
    an engineering company.
    """
    terms = _terms(design, notes)
    modules = design.get("modules", [])
    interface = selections.get("foundry_interface", "adaptive_foundry")
    posture = selections.get("innovation", "purposeful_innovation")
    needs_power = _need(terms, {"battery", "solar", "portable", "remote", "charging"})
    needs_outdoor = _need(terms, {"outdoor", "farm", "agriculture", "dust", "rain", "water", "rugged"})
    needs_data = _need(terms, {"data", "wireless", "cellular", "wifi", "bluetooth", "sensor", "gps"})
    family = "HF-Link Rugged" if needs_outdoor else ("HF-Link Core" if needs_power or needs_data else "HF-Link Mini")

    # Internal selection only — not exported as cost tables
    primary = "optimised"
    if needs_outdoor and posture == "aggressive_innovation":
        primary = "foundry_innovation"

    interface_spec = {
        "family": family,
        "strategy": interface,
        "shared_dna": {
            "keying": "family-controlled orientation; exact geometry must be tolerance-designed",
            "compatibility": "pin role, voltage/current envelope and signalling must be checked before mating",
            "cable": "overmould and strain relief selected for duty cycle; wire gauge and shielding remain calculated requirements",
            "safety": "no pin assignment is released without protection and misuse analysis",
        },
        "variant_generation_inputs": [
            "required circuits and pin roles",
            "maximum voltage/current",
            "data signalling class",
            "mating cycles",
            "ingress/environment target",
            "available enclosure volume",
            "cable bend/strain requirements",
        ],
        "release_status": "CONCEPT_ONLY_PENDING_CONNECTOR_ENGINEERING",
    }

    # Clean engineering-facing report: proposed path and validation needs only
    report = {
        "status": "PROPOSED_DESIGN_BASIS_GENERATED",
        "innovation_posture": posture,
        "modules_considered": len(modules),
        "proposed_approach": primary,
        "approach_summary": {
            "conventional": "Established component and enclosure architecture with standard interfaces.",
            "optimised": "Simplified part count and combined functions using proven manufacturing processes.",
            "foundry_innovation": "Product-specific interface family and geometry where integration value is clear.",
        }.get(primary, "Optimised architecture for a first prototype."),
        "interface_family": interface_spec,
        "required_validation": [
            "electrical calculations and protection analysis",
            "component and material data confirmation",
            "tolerance stack and mating analysis",
            "prototype fit/function testing",
            "environmental and cycle testing appropriate to intended use",
            "applicable EMC/safety/regulatory assessment",
        ],
        "handover_note": "This is a proposed design basis for detailed engineering. It is not a fabrication release.",
    }

    out = root / "02_System_Architecture"
    out.mkdir(parents=True, exist_ok=True)
    (out / "generative_innovation_dossier.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "foundry_interface_family.json").write_text(json.dumps(interface_spec, indent=2), encoding="utf-8")
    (out / "proposed_design_basis.md").write_text(
        "# Proposed design basis\n\n"
        f"**Recommended approach for first prototype:** {primary.replace('_', ' ').title()}\n\n"
        f"{report['approach_summary']}\n\n"
        "## Interface family\n\n"
        f"- Family: {family}\n"
        f"- Strategy: {interface}\n\n"
        "## Required validation before fabrication\n\n"
        + "\n".join(f"- {item}" for item in report["required_validation"])
        + "\n\n## Handover note\n\n"
        + report["handover_note"]
        + "\n",
        encoding="utf-8",
    )

    return [{
        "passed": True,
        "status": "PROPOSED_DESIGN_BASIS_GENERATED",
        "files": [
            "02_System_Architecture/generative_innovation_dossier.json",
            "02_System_Architecture/foundry_interface_family.json",
            "02_System_Architecture/proposed_design_basis.md",
        ],
        "note": "Proposed design basis and interface-family contract produced for engineering hand-off. Cost and durability reasoning remains internal to the AI design process and is not included in this package.",
    }]

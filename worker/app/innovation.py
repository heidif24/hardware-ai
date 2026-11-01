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
    """Create engineering candidates, cost/durability comparison and interface-family contract. Candidates are explicitly non-release concepts."""
    terms = _terms(design, notes)
    modules = design.get("modules", [])
    interface = selections.get("foundry_interface", "adaptive_foundry")
    posture = selections.get("innovation", "purposeful_innovation")
    needs_power = _need(terms, {"battery", "solar", "portable", "remote", "charging"})
    needs_outdoor = _need(terms, {"outdoor", "farm", "agriculture", "dust", "rain", "water", "rugged"})
    needs_data = _need(terms, {"data", "wireless", "cellular", "wifi", "bluetooth", "sensor", "gps"})
    family = "HF-Link Rugged" if needs_outdoor else ("HF-Link Core" if needs_power or needs_data else "HF-Link Mini")

    candidates = [
        {
            "approach": "conventional",
            "summary": "Established component and enclosure architecture with standard interfaces.",
            "expected_unit_cost_drivers": ["Off-the-shelf modules", "Minimal custom tooling", "Faster first article"],
            "durability_notes": "Reliability tracks the chosen module ratings and enclosure protection class.",
            "manufacturability_notes": "Quickest path to a first working prototype.",
            "strength": "Lowest validation uncertainty",
            "risk": "May miss product-specific cost, sealing or integration improvements.",
            "evidence_still_required": ["Exact module selection", "Power budget", "Environmental rating"],
        },
        {
            "approach": "optimised",
            "summary": "Simplify part count and combine functions using proven manufacturing processes for a durable, cost-aware pilot build.",
            "expected_unit_cost_drivers": ["Fewer discrete parts", "Shared power path", "Standard PCB process", "Avoid premature custom tooling"],
            "durability_notes": "Fewer interconnects can improve reliability when electrical and thermal margins are verified.",
            "manufacturability_notes": "Strong balance for pilot and small-batch production.",
            "strength": "Strong cost/durability balance for first prototype",
            "risk": "Requires comparative DFM and reliability analysis.",
            "evidence_still_required": ["BOM freeze", "Thermal path", "Assembly sequence"],
        },
        {
            "approach": "foundry_innovation",
            "summary": "Adapt a compatible interface-family member and explore multifunction physical geometry only where it improves cost, durability or user value.",
            "expected_unit_cost_drivers": ["Custom interface or enclosure features", "Possible tooling amortisation", "Higher upfront engineering"],
            "durability_notes": "Potential gains only after environmental and cycle testing pass.",
            "manufacturability_notes": "Justified only when evidence shows a measurable advantage over the optimised path.",
            "strength": "Distinctive ecosystem and potential integration gains",
            "risk": "Connector mating, electrical envelope, tooling and environmental performance require dedicated validation.",
            "evidence_still_required": ["Prototype fit/function", "Mating and cycle tests", "Post-DFM cost comparison"],
        },
    ]

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

    report = {
        "status": "CANDIDATES_GENERATED_NOT_VALIDATED",
        "innovation_posture": posture,
        "modules_considered": len(modules),
        "primary_recommendation": primary,
        "candidates": candidates,
        "interface_family": interface_spec,
        "decision_rule": "Recommend the optimised path for a first prototype unless the brief forces extreme cost reduction or validated novelty. A novel candidate may replace the baseline only when measurable evidence supports cost, durability, manufacturability, repairability or user-value improvement.",
        "required_validation": [
            "electrical calculations and protection analysis",
            "component and material data confirmation",
            "tolerance stack and mating analysis",
            "prototype fit/function testing",
            "environmental and cycle testing appropriate to intended use",
            "applicable EMC/safety/regulatory assessment",
        ],
        "handover_note": "This comparison is intended to help an engineering company choose a cost-effective, durable prototype path. It is not a fabrication release or a fixed price quote.",
    }

    out = root / "02_System_Architecture"
    out.mkdir(parents=True, exist_ok=True)
    (out / "generative_innovation_dossier.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "foundry_interface_family.json").write_text(json.dumps(interface_spec, indent=2), encoding="utf-8")
    (out / "cost_and_durability_alternatives.md").write_text(
        "# Cost and durability prototype alternatives\n\n"
        f"**Primary recommendation for first prototype:** {primary}\n\n"
        + "\n\n".join(
            f"## {c['approach'].replace('_', ' ').title()}\n\n"
            f"{c['summary']}\n\n"
            f"- **Cost drivers:** {'; '.join(c['expected_unit_cost_drivers'])}\n"
            f"- **Durability:** {c['durability_notes']}\n"
            f"- **Manufacturability:** {c['manufacturability_notes']}\n"
            f"- **Risk:** {c['risk']}\n"
            f"- **Evidence still required:** {'; '.join(c['evidence_still_required'])}\n"
            for c in candidates
        )
        + "\n\n## Decision rule\n\n"
        + report["decision_rule"]
        + "\n\n## Handover note\n\n"
        + report["handover_note"]
        + "\n",
        encoding="utf-8",
    )

    return [{
        "passed": True,
        "status": "CANDIDATES_GENERATED",
        "files": [
            "02_System_Architecture/generative_innovation_dossier.json",
            "02_System_Architecture/foundry_interface_family.json",
            "02_System_Architecture/cost_and_durability_alternatives.md",
        ],
        "note": "Cost/durability alternatives and a reusable interface-family contract were produced. They are concepts pending detailed engineering and validation.",
    }]

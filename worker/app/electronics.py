from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", text.strip())[:48].strip("_")
    return s or "BLOCK"


def _number_param(params: dict[str, Any], key: str) -> float | None:
    item = params.get(key)
    if isinstance(item, dict):
        if item.get("value_basis") not in ("user_specified", "source_verified", "calculated_with_method"):
            return None
        item = item.get("value")
    if isinstance(item, (int, float)) and not isinstance(item, bool) and 0 < float(item) < 10000:
        return float(item)
    return None


def _build_component_registry(plan: dict[str, Any], design: dict[str, Any]) -> list[dict[str, Any]]:
    registry: list[dict[str, Any]] = []
    candidates = _list(plan.get("component_candidates"))
    for i, raw in enumerate(candidates):
        c = _dict(raw)
        identity = str(c.get("identity_status") or "UNVERIFIED_FUNCTIONAL_CLASS")
        entry = {
            "ref": f"U{i+1}",
            "functional_class": str(c.get("description") or c.get("functional_class") or c.get("name") or "Unnamed functional block"),
            "module": str(c.get("module") or c.get("block") or ""),
            "identity_status": identity,
            "manufacturer": c.get("manufacturer") if identity != "UNVERIFIED_FUNCTIONAL_CLASS" else None,
            "part_number": c.get("part_number") if identity != "UNVERIFIED_FUNCTIONAL_CLASS" else None,
            "source_reference": c.get("source_reference"),
            "evidence_excerpt": c.get("evidence_excerpt"),
            "symbol_status": "VERIFIED" if c.get("symbol_verified") else "PENDING",
            "footprint_status": "VERIFIED" if c.get("footprint_verified") else "PENDING",
            "pin_map_status": "VERIFIED" if c.get("pin_map_verified") else "PENDING",
            "notes": str(c.get("identity_note") or c.get("note") or ""),
        }
        registry.append(entry)

    # Fall back to design modules when the plan has no candidates
    if not registry:
        for i, mod in enumerate(_list(design.get("modules"))):
            m = _dict(mod)
            parts = _list(m.get("parts")) or ["Functional candidate to be selected"]
            for j, part in enumerate(parts[:6]):
                registry.append({
                    "ref": f"U{i+1}{chr(65+j) if j else ''}",
                    "functional_class": str(part),
                    "module": str(m.get("name") or f"Module {i+1}"),
                    "identity_status": "UNVERIFIED_FUNCTIONAL_CLASS",
                    "manufacturer": None,
                    "part_number": None,
                    "source_reference": None,
                    "evidence_excerpt": None,
                    "symbol_status": "PENDING",
                    "footprint_status": "PENDING",
                    "pin_map_status": "PENDING",
                    "notes": "Derived from architecture functional candidates; not a frozen BOM line.",
                })
    return registry


def _build_logical_nets(design: dict[str, Any], registry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    nets: list[dict[str, Any]] = []
    nets.append({"name": "GND", "type": "power", "members": [], "status": "LOGICAL"})
    nets.append({"name": "VSYS", "type": "power", "members": [], "status": "LOGICAL"})

    for mod in _list(design.get("modules")):
        m = _dict(mod)
        name = str(m.get("name") or "Module")
        for iface in _list(m.get("interfaces")):
            iface_s = str(iface)
            net_name = _slug(f"{name}_{iface_s}").upper()
            nets.append({
                "name": net_name,
                "type": "signal",
                "interface_label": iface_s,
                "module": name,
                "members": [],
                "status": "LOGICAL",
                "note": "Logical connection only. Voltage, protocol, pin assignment and protection are not frozen.",
            })
    return nets


def _write_kicad_sch_scaffold(path: Path, product_name: str, registry: list[dict[str, Any]], nets: list[dict[str, Any]]) -> None:
    """Write a minimal KiCad 6/7 schematic scaffold with hierarchical text blocks.

    This is intentionally not a pin-correct, symbol-backed design. It is a structured
    starting point an engineer can open and replace with verified symbols.
    """
    lines = [
        "(kicad_sch (version 20230121) (generator hardware_foundry_electronics_engine)",
        "  (uuid 00000000-0000-4000-8000-000000000001)",
        "  (paper \"A3\")",
        f"  (title_block (title \"{product_name[:80]}\") (comment 1 \"CONCEPT SCAFFOLD — NOT FABRICATION READY\")",
        "    (comment 2 \"Symbols, footprints and pin maps must be verified before ERC/PCB\"))",
    ]
    # Title text
    lines.append(
        '  (text "HARDWARE FOUNDRY — SYSTEM SCHEMATIC SCAFFOLD\n'
        'Replace functional blocks with verified symbols and footprints.\n'
        'Do not fabricate from this file."'
        " (at 50 20 0) (effects (font (size 2 2)) (justify left top)))"
    )
    y = 40.0
    for i, comp in enumerate(registry[:24]):
        label = f"{comp['ref']}: {comp['functional_class'][:40]} [{comp['identity_status']}]"
        lines.append(
            f'  (text "{label}" (at 30 {y:.1f} 0) '
            f"(effects (font (size 1.27 1.27)) (justify left top)))"
        )
        y += 8.0
        if y > 250:
            break
    y = 40.0
    for net in nets[:30]:
        lines.append(
            f'  (text "NET {net[\"name\"]} ({net[\"type\"]})" (at 160 {y:.1f} 0) '
            f"(effects (font (size 1.27 1.27)) (justify left top)))"
        )
        y += 7.0
    lines.append(")\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_pcb_outline(path: Path, length_mm: float, width_mm: float) -> None:
    """Minimal KiCad PCB with board outline only (no copper, no footprints)."""
    # KiCad PCB edge.cuts rectangle
    content = f"""(kicad_pcb (version 20221018) (generator hardware_foundry_electronics_engine)
  (general (thickness 1.6))
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user)
    (33 "F.Adhes" user)
    (34 "B.Paste" user)
    (35 "F.Paste" user)
    (36 "B.SilkS" user)
    (37 "F.SilkS" user)
    (38 "B.Mask" user)
    (39 "F.Mask" user)
    (44 "Edge.Cuts" user)
    (45 "Margin" user)
  )
  (setup (pad_to_mask_clearance 0))
  (gr_line (start 0 0) (end {length_mm} 0) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start {length_mm} 0) (end {length_mm} {width_mm}) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start {length_mm} {width_mm}) (end 0 {width_mm}) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start 0 {width_mm}) (end 0 0) (layer "Edge.Cuts") (width 0.1))
  (gr_text "OUTLINE ONLY — NO FOOTPRINTS / NO COPPER / NOT FABRICABLE"
    (at {length_mm/2:.2f} {width_mm/2:.2f}) (layer "F.SilkS")
    (effects (font (size 1.5 1.5))))
)
"""
    path.write_text(content, encoding="utf-8")


def generate_electronics(
    root: Path,
    plan: dict[str, Any],
    design: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Autonomous electronics engineering pipeline (evidence-gated).

    Stages:
      1. Component registry from plan/architecture
      2. Logical netlist from module interfaces
      3. System schematic scaffold (KiCad text blocks)
      4. PCB outline when verified board dimensions exist
      5. Manufacturing package status (honest)

    Never invents manufacturer part numbers, pin maps or electrical ratings.
    """
    design = design or {}
    out = root / "03_Electronics"
    out.mkdir(parents=True, exist_ok=True)
    fab = root / "04_Fabrication"
    fab.mkdir(parents=True, exist_ok=True)

    registry = _build_component_registry(plan, design)
    nets = _build_logical_nets(design, registry)
    product = str(design.get("product_name") or plan.get("product_summary") or "Hardware Foundry Product")

    verified = [c for c in registry if c["identity_status"] not in ("UNVERIFIED_FUNCTIONAL_CLASS", "") and c.get("part_number")]
    pin_ready = [c for c in registry if c.get("pin_map_status") == "VERIFIED"]
    footprint_ready = [c for c in registry if c.get("footprint_status") == "VERIFIED"]

    (out / "component_registry.json").write_text(json.dumps({
        "status": "REGISTRY_GENERATED",
        "total": len(registry),
        "verified_identities": len(verified),
        "pin_maps_verified": len(pin_ready),
        "footprints_verified": len(footprint_ready),
        "components": registry,
        "rule": "A component may enter fabrication BOM only with verified identity, symbol, footprint and pin map.",
    }, indent=2), encoding="utf-8")

    (out / "logical_netlist.json").write_text(json.dumps({
        "status": "LOGICAL_NETLIST",
        "nets": nets,
        "note": "Logical nets from architecture interfaces. Not an electrical netlist with pin numbers.",
    }, indent=2), encoding="utf-8")

    sch_path = out / "system_schematic_scaffold.kicad_sch"
    _write_kicad_sch_scaffold(sch_path, product, registry, nets)

    blocks_md = [
        "# System schematic scaffold",
        "",
        f"**Product:** {product}",
        "",
        "This package contains a structured electronics starting point for an engineering company.",
        "It is **not** a verified schematic and **must not** be sent to fabrication as-is.",
        "",
        "## Component registry summary",
        f"- Functional entries: {len(registry)}",
        f"- Verified manufacturer identities: {len(verified)}",
        f"- Verified pin maps: {len(pin_ready)}",
        f"- Verified footprints: {len(footprint_ready)}",
        "",
        "## Modules",
    ]
    for mod in _list(design.get("modules")):
        m = _dict(mod)
        blocks_md.append(f"### {m.get('name', 'Module')}")
        blocks_md.append(str(m.get("purpose") or ""))
        ifaces = _list(m.get("interfaces"))
        if ifaces:
            blocks_md.append("Interfaces: " + ", ".join(map(str, ifaces)))
        blocks_md.append("")
    blocks_md.extend([
        "## Required before ERC and PCB",
        "1. Freeze exact component identities from current datasheets",
        "2. Assign verified KiCad symbols and footprints",
        "3. Capture pin-correct connectivity",
        "4. Run ERC and resolve all errors",
        "5. Only then proceed to layout and DRC",
        "",
    ])
    (out / "system_schematic_blocks.md").write_text("\n".join(blocks_md), encoding="utf-8")

    # PCB outline from mechanical parameters when available
    mech = _dict(plan.get("mechanical_design"))
    params = _dict(mech.get("parameters"))
    length = _number_param(params, "length") or _number_param(params, "board_length")
    width = _number_param(params, "width") or _number_param(params, "board_width")
    pcb_files: list[str] = []
    pcb_status = "BLOCKED"
    pcb_missing: list[str] = []
    if length and width:
        pcb_path = fab / "board_outline_only.kicad_pcb"
        _write_pcb_outline(pcb_path, length, width)
        pcb_files.append("04_Fabrication/board_outline_only.kicad_pcb")
        pcb_status = "OUTLINE_ONLY"
    else:
        pcb_missing = [
            "mechanical_design.parameters.length (or board_length) with verified provenance",
            "mechanical_design.parameters.width (or board_width) with verified provenance",
        ]

    # Manufacturing package honesty report
    mfg = {
        "release_state": "ELECTRONICS_SCAFFOLD_NOT_FABRICATION_RELEASE",
        "schematic": {
            "file": "03_Electronics/system_schematic_scaffold.kicad_sch",
            "status": "SCAFFOLD",
            "pin_correct": False,
            "erc_run": False,
        },
        "pcb": {
            "status": pcb_status,
            "files": pcb_files,
            "routed": False,
            "drc_run": False,
            "missing_inputs": pcb_missing,
        },
        "bom": {
            "status": "FUNCTIONAL_CANDIDATES_ONLY" if not verified else "PARTIAL_VERIFIED",
            "verified_line_items": len(verified),
            "total_line_items": len(registry),
        },
        "gerbers": {"status": "NOT_GENERATED", "reason": "Requires reviewed, routed PCB with DRC pass"},
        "gates_remaining": [
            "Verified component identities and datasheets",
            "Verified symbols, footprints and pin maps",
            "Engineer-reviewed schematic and ERC clean",
            "Routed PCB and DRC clean",
            "Gerber/drill export from reviewed board",
        ],
    }
    (fab / "manufacturing_package_status.json").write_text(json.dumps(mfg, indent=2), encoding="utf-8")
    (fab / "README.md").write_text(
        "# Fabrication package status\n\n"
        "This folder holds electronics manufacturing artefacts only when evidence gates pass.\n\n"
        f"**Current state:** `{mfg['release_state']}`\n\n"
        "- Schematic scaffold may be present under `03_Electronics/`\n"
        "- Board outline may be present when dimensions are verified\n"
        "- Gerbers, drill, pick-and-place and IPC netlist are **not** generated from unverified designs\n",
        encoding="utf-8",
    )

    (out / "electronics_engine_status.json").write_text(json.dumps({
        "status": "ELECTRONICS_ENGINE_COMPLETED_SCAFFOLD",
        "passed": True,
        "fabrication_ready": False,
        "stages": {
            "component_registry": "DONE",
            "logical_netlist": "DONE",
            "schematic_scaffold": "DONE",
            "pcb_outline": pcb_status,
            "autoroute": "NOT_RUN — requires verified schematic and footprints",
            "erc": "NOT_RUN — requires pin-correct schematic",
            "drc": "NOT_RUN — requires routed PCB",
            "gerbers": "NOT_GENERATED",
        },
        "files": [
            "03_Electronics/component_registry.json",
            "03_Electronics/logical_netlist.json",
            "03_Electronics/system_schematic_blocks.md",
            "03_Electronics/system_schematic_scaffold.kicad_sch",
            "03_Electronics/electronics_engine_status.json",
            "04_Fabrication/manufacturing_package_status.json",
            "04_Fabrication/README.md",
            *pcb_files,
        ],
        "notice": (
            "The electronics engine produced a structured design package for engineering continuation. "
            "It does not claim electrical correctness, regulatory compliance or fabrication readiness."
        ),
    }, indent=2), encoding="utf-8")

    return {
        "status": "ELECTRONICS_ENGINE_COMPLETED_SCAFFOLD",
        "passed": True,
        "fabrication_ready": False,
        "files": [
            "03_Electronics/component_registry.json",
            "03_Electronics/logical_netlist.json",
            "03_Electronics/system_schematic_blocks.md",
            "03_Electronics/system_schematic_scaffold.kicad_sch",
            "03_Electronics/electronics_engine_status.json",
            "04_Fabrication/manufacturing_package_status.json",
            *pcb_files,
        ],
        "component_count": len(registry),
        "verified_identities": len(verified),
        "pcb_outline": pcb_status,
        "note": (
            "Electronics scaffold generated. Fabrication assets remain blocked until verified components, "
            "pin-correct schematic, ERC/DRC and engineering sign-off exist."
        ),
    }

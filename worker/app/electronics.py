from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _slug(text: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", text.strip())[:40].strip("_")
    return s or "BLOCK"


def _uid() -> str:
    return str(uuid.uuid4())


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
        registry.append({
            "ref": f"U{i + 1}",
            "functional_class": str(
                c.get("description") or c.get("functional_class") or c.get("name") or "Unnamed functional block"
            ),
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
        })
    if not registry:
        for i, mod in enumerate(_list(design.get("modules"))):
            m = _dict(mod)
            parts = _list(m.get("parts")) or ["Functional candidate to be selected"]
            for j, part in enumerate(parts[:6]):
                registry.append({
                    "ref": f"U{i + 1}{chr(65 + j) if j else ''}",
                    "functional_class": str(part),
                    "module": str(m.get("name") or f"Module {i + 1}"),
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


def _build_logical_nets(design: dict[str, Any]) -> list[dict[str, Any]]:
    nets: list[dict[str, Any]] = [
        {"name": "GND", "type": "power", "members": [], "status": "LOGICAL"},
        {"name": "VSYS", "type": "power", "members": [], "status": "LOGICAL"},
    ]
    for mod in _list(design.get("modules")):
        m = _dict(mod)
        name = str(m.get("name") or "Module")
        for iface in _list(m.get("interfaces")):
            iface_s = str(iface)
            nets.append({
                "name": _slug(f"{name}_{iface_s}").upper(),
                "type": "signal",
                "interface_label": iface_s,
                "module": name,
                "members": [],
                "status": "LOGICAL",
                "note": "Logical connection only. Voltage, protocol, pin assignment and protection are not frozen.",
            })
    return nets


def _text(s: str, x: float, y: float, size: float = 1.27) -> str:
    safe = s.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f'  (text "{safe}" (at {x:.2f} {y:.2f} 0)'
        f" (effects (font (size {size} {size})) (justify left top)))"
    )


def _rect(x: float, y: float, w: float, h: float) -> str:
    return (
        f"  (rectangle (start {x:.2f} {y:.2f}) (end {x + w:.2f} {y + h:.2f})"
        f" (stroke (width 0.15) (type solid)) (fill (type none)))"
    )


def _global_label(name: str, x: float, y: float, shape: str = "bidirectional") -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", name)[:48]
    return (
        f'  (global_label "{safe}" (shape {shape}) (at {x:.2f} {y:.2f} 0) (fields_autoplaced)'
        f" (effects (font (size 1.27 1.27)) (justify left bottom))"
        f' (uuid "{_uid()}"))'
    )


def _sheet_header(title: str, comment: str) -> list[str]:
    return [
        "(kicad_sch (version 20230121) (generator hardware_foundry_electronics_engine)",
        f'  (uuid "{_uid()}")',
        '  (paper "A3")',
        f'  (title_block (title "{title[:80]}") (comment 1 "{comment[:100]}")',
        '    (comment 2 "SCAFFOLD — replace blocks with verified symbols before ERC"))',
    ]


def _write_module_sheet(
    path: Path,
    module_name: str,
    purpose: str,
    interfaces: list[str],
    components: list[dict[str, Any]],
) -> None:
    lines = _sheet_header(module_name, "Module sheet scaffold")
    lines.append(_text(f"MODULE: {module_name}", 20, 15, 2.0))
    lines.append(_text(purpose[:120] if purpose else "Purpose not specified", 20, 22, 1.27))
    lines.append(_text("CONCEPT SCAFFOLD — NOT PIN-CORRECT — DO NOT FABRICATE", 20, 30, 1.5))
    lines.append(_global_label("GND", 25, 45, "input"))
    lines.append(_global_label("VSYS", 25, 55, "input"))
    lines.append(_text("Power tree (logical)", 40, 42, 1.0))
    lines.append(_rect(60, 40, 80, 50))
    lines.append(_text(f"[{module_name}]", 65, 45, 1.5))
    lines.append(_text("Replace with verified symbols", 65, 55, 1.0))
    y = 45.0
    for iface in interfaces[:12]:
        net = _slug(f"{module_name}_{iface}").upper()
        lines.append(_global_label(net, 150, y, "bidirectional"))
        lines.append(_text(str(iface)[:40], 155, y - 3, 1.0))
        y += 10.0
    y = 100.0
    lines.append(_text("Component placeholders for this module:", 20, y, 1.27))
    y += 8.0
    for comp in components[:10]:
        lines.append(_text(
            f"{comp['ref']}: {comp['functional_class'][:50]} [{comp['identity_status']}]",
            25, y, 1.0,
        ))
        y += 7.0
    lines.append(")\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_root_schematic(
    path: Path,
    product_name: str,
    modules: list[dict[str, Any]],
    sheet_files: list[tuple[str, str]],
) -> None:
    lines = _sheet_header(product_name, "CONCEPT SCAFFOLD — NOT FABRICATION READY")
    lines.append(_text("HARDWARE FOUNDRY — SYSTEM SCHEMATIC (HIERARCHICAL)", 20, 12, 2.5))
    lines.append(_text(
        "Each sheet is a module scaffold. Replace blocks with verified symbols, footprints and pin maps before ERC.",
        20, 22, 1.27,
    ))
    lines.append(_global_label("GND", 25, 35, "input"))
    lines.append(_global_label("VSYS", 25, 45, "input"))
    lines.append(_text("System power (logical distribution)", 40, 35, 1.0))
    x, y = 30.0, 60.0
    for i, (sheet_name, filename) in enumerate(sheet_files[:12]):
        lines.append(
            f'  (sheet (at {x:.2f} {y:.2f}) (size 50 30) (fields_autoplaced)'
            f' (stroke (width 0.15) (type solid)) (fill (type none))'
            f' (uuid "{_uid()}")'
            f'\n    (property "Sheetname" "{sheet_name[:40]}" (at {x + 1:.2f} {y + 2:.2f} 0)'
            f' (effects (font (size 1.27 1.27)) (justify left top)))'
            f'\n    (property "Sheetfile" "{filename}" (at {x + 1:.2f} {y + 6:.2f} 0)'
            f' (effects (font (size 1.0 1.0)) (justify left top)))'
            f'\n    (pin "GND" input (at {x:.2f} {y + 15:.2f} 180) (uuid "{_uid()}"))'
            f'\n    (pin "VSYS" input (at {x:.2f} {y + 20:.2f} 180) (uuid "{_uid()}"))'
            f"\n  )"
        )
        x += 60.0
        if x > 250:
            x = 30.0
            y += 40.0
    lines.append(_text(
        "Release rule: do not run ERC as a fabrication gate until symbols, footprints and pin maps are verified.",
        20, 250, 1.0,
    ))
    lines.append(")\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_connectivity_matrix(path: Path, design: dict[str, Any], nets: list[dict[str, Any]]) -> None:
    rows = ["# Connectivity matrix (logical)", "", "| Module | Interface | Logical net | Type | Status |", "|---|---|---|---|---|"]
    for mod in _list(design.get("modules")):
        m = _dict(mod)
        name = str(m.get("name") or "Module")
        for iface in _list(m.get("interfaces")):
            net = _slug(f"{name}_{iface}").upper()
            rows.append(f"| {name} | {iface} | `{net}` | signal | LOGICAL |")
    rows.append("")
    rows.append("## Power")
    rows.append("| Net | Type | Status |")
    rows.append("|---|---|---|")
    rows.append("| `GND` | power | LOGICAL |")
    rows.append("| `VSYS` | power | LOGICAL |")
    rows.append("")
    rows.append("Pin numbers, voltage levels and protection devices are **not** assigned in this matrix.")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_pcb_outline(path: Path, length_mm: float, width_mm: float) -> None:
    content = f"""(kicad_pcb (version 20221018) (generator hardware_foundry_electronics_engine)
  (general (thickness 1.6))
  (paper "A4")
  (layers
    (0 "F.Cu" signal)
    (31 "B.Cu" signal)
    (44 "Edge.Cuts" user)
    (37 "F.SilkS" user)
  )
  (setup (pad_to_mask_clearance 0))
  (gr_line (start 0 0) (end {length_mm} 0) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start {length_mm} 0) (end {length_mm} {width_mm}) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start {length_mm} {width_mm}) (end 0 {width_mm}) (layer "Edge.Cuts") (width 0.1))
  (gr_line (start 0 {width_mm}) (end 0 0) (layer "Edge.Cuts") (width 0.1))
  (gr_text "OUTLINE ONLY — NO FOOTPRINTS / NO COPPER / NOT FABRICABLE"
    (at {length_mm / 2:.2f} {width_mm / 2:.2f}) (layer "F.SilkS")
    (effects (font (size 1.5 1.5))))
)
"""
    path.write_text(content, encoding="utf-8")


def generate_electronics(
    root: Path,
    plan: dict[str, Any],
    design: dict[str, Any] | None = None,
) -> dict[str, Any]:
    design = design or {}
    out = root / "03_Electronics"
    sheets_dir = out / "sheets"
    out.mkdir(parents=True, exist_ok=True)
    sheets_dir.mkdir(parents=True, exist_ok=True)
    fab = root / "04_Fabrication"
    fab.mkdir(parents=True, exist_ok=True)

    registry = _build_component_registry(plan, design)
    nets = _build_logical_nets(design)
    product = str(design.get("product_name") or plan.get("product_summary") or "Hardware Foundry Product")
    modules = _list(design.get("modules"))

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

    _write_connectivity_matrix(out / "connectivity_matrix.md", design, nets)

    sheet_files: list[tuple[str, str]] = []
    schematic_files = [
        "03_Electronics/component_registry.json",
        "03_Electronics/logical_netlist.json",
        "03_Electronics/connectivity_matrix.md",
        "03_Electronics/system_schematic_blocks.md",
        "03_Electronics/system_schematic_root.kicad_sch",
        "03_Electronics/electronics_engine_status.json",
        "04_Fabrication/manufacturing_package_status.json",
        "04_Fabrication/README.md",
    ]

    for i, mod in enumerate(modules[:12]):
        m = _dict(mod)
        name = str(m.get("name") or f"Module_{i + 1}")
        slug = _slug(name).lower()
        filename = f"{slug}.kicad_sch"
        comps = [c for c in registry if c.get("module") == name] or [c for c in registry if not c.get("module")][:3]
        _write_module_sheet(
            sheets_dir / filename,
            name,
            str(m.get("purpose") or ""),
            [str(x) for x in _list(m.get("interfaces"))],
            comps,
        )
        sheet_files.append((name, f"sheets/{filename}"))
        schematic_files.append(f"03_Electronics/sheets/{filename}")

    if not sheet_files:
        _write_module_sheet(sheets_dir / "system.kicad_sch", "System", product, [], registry[:8])
        sheet_files.append(("System", "sheets/system.kicad_sch"))
        schematic_files.append("03_Electronics/sheets/system.kicad_sch")

    _write_root_schematic(out / "system_schematic_root.kicad_sch", product, modules, sheet_files)

    blocks = [
        "# System schematic structure", "",
        f"**Product:** {product}", "",
        "Hierarchical layout:", "",
        "- `system_schematic_root.kicad_sch` — root sheet with module sheet symbols and system power",
        "- `sheets/<module>.kicad_sch` — one sheet per functional module", "",
        "## Modules",
    ]
    for name, fname in sheet_files:
        blocks.append(f"- **{name}** → `{fname}`")
    blocks.extend([
        "", "## Power tree (logical)",
        "- `GND` — system ground",
        "- `VSYS` — primary system rail (level not frozen)", "",
        "## Status",
        f"- Functional registry entries: {len(registry)}",
        f"- Verified manufacturer identities: {len(verified)}",
        f"- Verified pin maps: {len(pin_ready)}",
        f"- Verified footprints: {len(footprint_ready)}", "",
        "## Required before ERC / PCB",
        "1. Freeze exact component identities from current datasheets",
        "2. Assign verified KiCad symbols and footprints",
        "3. Capture pin-correct connectivity",
        "4. Run ERC and resolve all errors",
        "5. Only then proceed to layout and DRC", "",
    ])
    (out / "system_schematic_blocks.md").write_text("\n".join(blocks), encoding="utf-8")

    mech = _dict(plan.get("mechanical_design"))
    params = _dict(mech.get("parameters"))
    length = _number_param(params, "length") or _number_param(params, "board_length")
    width = _number_param(params, "width") or _number_param(params, "board_width")
    pcb_files: list[str] = []
    pcb_status = "BLOCKED"
    pcb_missing: list[str] = []
    if length and width:
        _write_pcb_outline(fab / "board_outline_only.kicad_pcb", length, width)
        pcb_files.append("04_Fabrication/board_outline_only.kicad_pcb")
        pcb_status = "OUTLINE_ONLY"
        schematic_files.extend(pcb_files)
    else:
        pcb_missing = [
            "mechanical_design.parameters.length (or board_length) with verified provenance",
            "mechanical_design.parameters.width (or board_width) with verified provenance",
        ]

    mfg = {
        "release_state": "ELECTRONICS_SCAFFOLD_NOT_FABRICATION_RELEASE",
        "schematic": {
            "root": "03_Electronics/system_schematic_root.kicad_sch",
            "module_sheets": [f for _, f in sheet_files],
            "status": "HIERARCHICAL_SCAFFOLD",
            "pin_correct": False,
            "erc_run": False,
        },
        "pcb": {"status": pcb_status, "files": pcb_files, "routed": False, "drc_run": False, "missing_inputs": pcb_missing},
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
        f"**Current state:** `{mfg['release_state']}`\n\n"
        "Hierarchical schematic scaffolds are under `03_Electronics/`.\n"
        "Board outline may appear here when dimensions are verified.\n"
        "Gerbers are not generated from unverified designs.\n",
        encoding="utf-8",
    )

    (out / "electronics_engine_status.json").write_text(json.dumps({
        "status": "ELECTRONICS_ENGINE_COMPLETED_HIERARCHICAL_SCAFFOLD",
        "passed": True,
        "fabrication_ready": False,
        "stages": {
            "component_registry": "DONE",
            "logical_netlist": "DONE",
            "connectivity_matrix": "DONE",
            "hierarchical_schematic": "DONE",
            "module_sheets": len(sheet_files),
            "pcb_outline": pcb_status,
            "autoroute": "NOT_RUN — requires verified schematic and footprints",
            "erc": "NOT_RUN — requires pin-correct schematic",
            "drc": "NOT_RUN — requires routed PCB",
            "gerbers": "NOT_GENERATED",
        },
        "files": schematic_files,
        "notice": "Hierarchical schematic structure for engineering continuation. Not fabrication readiness.",
    }, indent=2), encoding="utf-8")

    return {
        "status": "ELECTRONICS_ENGINE_COMPLETED_HIERARCHICAL_SCAFFOLD",
        "passed": True,
        "fabrication_ready": False,
        "files": schematic_files,
        "module_sheets": len(sheet_files),
        "component_count": len(registry),
        "verified_identities": len(verified),
        "pcb_outline": pcb_status,
        "note": (
            "Hierarchical electronics scaffold generated (root + module sheets, power tree, connectivity matrix). "
            "Fabrication remains blocked until verified components, pin-correct schematic, ERC/DRC and sign-off exist."
        ),
    }

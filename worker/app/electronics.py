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


def _kicad_text(text: str, x: float, y: float, size: float = 1.27) -> str:
    safe = text.replace("\\", "\\\\").replace('"', "\\\"")
    return (
        f'  (text "{safe}" (at {x:.2f} {y:.2f} 0)'
        f" (effects (font (size {size} {size})) (justify left top)))"
    )


def _kicad_rect(x: float, y: float, w: float, h: float) -> str:
    return (
        f"  (rectangle (start {x:.2f} {y:.2f}) (end {x + w:.2f} {y + h:.2f})"
        f" (stroke (width 0.15) (type solid)) (fill (type none)))"
    )


def _kicad_label(name: str, x: float, y: float, shape: str = "input") -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", name)[:48]
    return (
        f'  (label "{safe}" (at {x:.2f} {y:.2f} 0) (fields_autoplaced)'
        f" (effects (font (size 1.27 1.27)) (justify left bottom)))"
    )


def _kicad_global_label(name: str, x: float, y: float, shape: str = "bidirectional") -> str:
    safe = re.sub(r"[^A-Za-z0-9_]", "_", name)[:48]
    return (
        f'  (global_label "{safe}" (shape {shape}) (at {x:.2f} {y:.2f} 0) (fields_autoplaced)'
        f" (effects (font (size 1.27 1.27)) (justify left bottom))
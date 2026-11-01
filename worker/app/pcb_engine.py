from __future__ import annotations

import importlib
import json
import math
from pathlib import Path
from typing import Any

ALLOWED_PROVENANCE = {"user_specified", "source_verified", "calculated_with_method"}
MAX_COMPONENTS = 250
MAX_NETS = 500
MAX_TRACKS = 5000


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _verified_number(value: Any, name: str, *, minimum: float = 0.001, maximum: float = 10000) -> float:
    if not isinstance(value, dict) or value.get("value_basis") not in ALLOWED_PROVENANCE:
        raise ValueError(f"{name} must include a provenance-labelled value.")
    number = value.get("value")
    if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(float(number)):
        raise ValueError(f"{name}.value must be a finite number.")
    if not minimum <= float(number) <= maximum:
        raise ValueError(f"{name}.value is outside the supported range.")
    return float(number)


def _pcbnew():
    try:
        return importlib.import_module("pcbnew")
    except ImportError as exc:
        raise RuntimeError("KiCad pcbnew Python bindings are not installed in the engineering worker.") from exc


def _safe_footprint_library(raw: str, root: Path) -> Path:
    candidate = Path(raw)
    allowed_roots = [Path("/usr/share/kicad/footprints").resolve(), (root.parent / "00_Engineering_Sources").resolve()]
    resolved = (root.parent / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not any(resolved == base or base in resolved.parents for base in allowed_roots):
        raise ValueError("Footprint library must be an installed KiCad library or a supplied source under 00_Engineering_Sources.")
    if not resolved.is_dir() or resolved.suffix != ".pretty":
        raise ValueError("footprint_library must identify an existing .pretty directory.")
    return resolved


def generate_pcb(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Build an editable KiCad board from a fully specified, provenance-labelled layout contract.

    This is a deterministic placement/routing executor, not an autorouter. It never
    chooses footprints, pin mappings, placements, stackup or copper paths itself.
    """
    spec = _obj(_obj(plan.get("pcb_design")).get("native_layout"))
    if not spec:
        return {"status": "BLOCKED", "passed": False, "missing_inputs": [
            "pcb_design.native_layout: verified board outline, stackup, footprint mappings, placements, nets and routed copper paths"
        ]}
    try:
        width = _verified_number(spec.get("width_mm"), "pcb_design.native_layout.width_mm")
        height = _verified_number(spec.get("height_mm"), "pcb_design.native_layout.height_mm")
        thickness = _verified_number(spec.get("thickness_mm"), "pcb_design.native_layout.thickness_mm", minimum=0.2, maximum=5)
        copper = spec.get("copper_layers")
        if copper not in (2, 4, 6):
            raise ValueError("copper_layers must be 2, 4 or 6 and must be confirmed by the board stackup.")
        components = spec.get("components")
        nets = spec.get("nets")
        tracks = spec.get("tracks")
        if not isinstance(components, list) or not components or len(components) > MAX_COMPONENTS:
            raise ValueError(f"components must contain 1..{MAX_COMPONENTS} verified entries.")
        if not isinstance(nets, list) or not nets or len(nets) > MAX_NETS:
            raise ValueError(f"nets must contain 1..{MAX_NETS} verified entries.")
        if not isinstance(tracks, list) or len(tracks) > MAX_TRACKS:
            raise ValueError(f"tracks must be an explicit list of 0..{MAX_TRACKS} routed segments.")
        outline_basis = spec.get("outline_basis")
        if outline_basis not in ALLOWED_PROVENANCE:
            raise ValueError("outline_basis must be user_specified, source_verified or calculated_with_method.")
        seen_refs: set[str] = set()
        net_names = {str(item.get("name")) for item in nets if isinstance(item, dict)}
        if len(net_names) != len(nets) or "" in net_names:
            raise ValueError("Every net requires a unique non-empty name.")
        for component in components:
            if not isinstance(component, dict):
                raise ValueError("Each component must be an object.")
            ref = component.get("reference")
            if not isinstance(ref, str) or not ref or ref in seen_refs:
                raise ValueError("Component references must be unique non-empty strings.")
            seen_refs.add(ref)
            for key in ("x_mm", "y_mm", "rotation_deg"):
                val = component.get(key)
                if isinstance(val, dict):
                    _verified_number(val, f"component {ref}.{key}", minimum=-360, maximum=360)
                elif key != "rotation_deg":
                    raise ValueError(f"component {ref}.{key} must carry provenance.")
            if not isinstance(component.get("footprint"), str) or ":" not in component["footprint"]:
                raise ValueError(f"Component {ref} requires an exact KiCad library:footprint identifier.")
            pads = component.get("pads")
            if not isinstance(pads, dict) or not pads:
                raise ValueError(f"Component {ref} requires an explicit pad-number-to-net mapping.")
            unknown = set(map(str, pads.values())) - net_names
            if unknown:
                raise ValueError(f"Component {ref} maps pads to unknown nets: {sorted(unknown)}")
        for index, track in enumerate(tracks):
            if not isinstance(track, dict) or track.get("net") not in net_names:
                raise ValueError(f"Track {index} must reference a declared net.")
            if track.get("layer") not in ("F.Cu", "B.Cu"):
                raise ValueError(f"Track {index} layer must be F.Cu or B.Cu.")
            for key in ("start_x_mm", "start_y_mm", "end_x_mm", "end_y_mm", "width_mm"):
                _verified_number(track.get(key), f"track[{index}].{key}")
            if track["width_mm"]["value"] > 2:
                raise ValueError(f"Track {index} width exceeds the safe generator limit; review the design contract.")
        libraries = spec.get("footprint_libraries")
        if not isinstance(libraries, dict):
            raise ValueError("footprint_libraries must map exact KiCad library nicknames to approved .pretty directories.")
        root.mkdir(parents=True, exist_ok=True)
        pcb = _pcbnew()
        board = pcb.BOARD()
        board.SetFileName(str(root / "foundry_generated.kicad_pcb"))
        board.GetDesignSettings().SetBoardThickness(pcb.FromMM(thickness))
        net_objects = {}
        for name in sorted(net_names):
            net = pcb.NETINFO_ITEM(board, name)
            board.Add(net)
            net_objects[name] = net
        for component in components:
            nickname, footprint_name = component["footprint"].split(":", 1)
            library = libraries.get(nickname)
            if not isinstance(library, str):
                raise ValueError(f"No approved library path supplied for footprint nickname {nickname}.")
            lib_path = _safe_footprint_library(library, root)
            footprint = pcb.FootprintLoad(str(lib_path), footprint_name)
            if footprint is None:
                raise ValueError(f"KiCad footprint could not be loaded: {component['footprint']}.")
            footprint.SetReference(component["reference"])
            footprint.SetValue(str(component.get("value", component["reference"])))
            footprint.SetPosition(pcb.VECTOR2I(pcb.FromMM(_verified_number(component["x_mm"], component["reference"] + ".x_mm", minimum=0)),
                                               pcb.FromMM(_verified_number(component["y_mm"], component["reference"] + ".y_mm", minimum=0))))
            rotation = component.get("rotation_deg", 0)
            if isinstance(rotation, dict):
                rotation = _verified_number(rotation, component["reference"] + ".rotation_deg", minimum=-360, maximum=360)
            if isinstance(rotation, bool) or not isinstance(rotation, (int, float)) or not math.isfinite(float(rotation)):
                raise ValueError(f"Invalid rotation for {component['reference']}.")
            footprint.SetOrientationDegrees(float(rotation))
            pads = {pad.GetNumber(): pad for pad in footprint.Pads()}
            for pad_number, net_name in component["pads"].items():
                if str(pad_number) not in pads:
                    raise ValueError(f"Footprint {component['footprint']} has no pad {pad_number} for {component['reference']}.")
                pads[str(pad_number)].SetNet(net_objects[str(net_name)])
            board.Add(footprint)
        # Board outline is an explicit rectangular envelope in this first native executor.
        corners = [(0, 0), (width, 0), (width, height), (0, height)]
        for i in range(4):
            x1, y1 = corners[i]
            x2, y2 = corners[(i + 1) % 4]
            edge = pcb.PCB_SHAPE(board)
            edge.SetShape(pcb.SHAPE_T_SEGMENT)
            edge.SetStart(pcb.VECTOR2I(pcb.FromMM(x1), pcb.FromMM(y1)))
            edge.SetEnd(pcb.VECTOR2I(pcb.FromMM(x2), pcb.FromMM(y2)))
            edge.SetLayer(pcb.Edge_Cuts)
            edge.SetWidth(pcb.FromMM(0.05))
            board.Add(edge)
        for index, item in enumerate(tracks):
            segment = pcb.PCB_TRACK(board)
            segment.SetStart(pcb.VECTOR2I(pcb.FromMM(_verified_number(item["start_x_mm"], f"track[{index}].start_x_mm", minimum=0)),
                                           pcb.FromMM(_verified_number(item["start_y_mm"], f"track[{index}].start_y_mm", minimum=0))))
            segment.SetEnd(pcb.VECTOR2I(pcb.FromMM(_verified_number(item["end_x_mm"], f"track[{index}].end_x_mm", minimum=0)),
                                         pcb.FromMM(_verified_number(item["end_y_mm"], f"track[{index}].end_y_mm", minimum=0))))
            segment.SetWidth(pcb.FromMM(_verified_number(item["width_mm"], f"track[{index}].width_mm")))
            segment.SetLayer(pcb.F_Cu if item["layer"] == "F.Cu" else pcb.B_Cu)
            segment.SetNet(net_objects[item["net"]])
            board.Add(segment)
        output = root / "foundry_generated.kicad_pcb"
        pcb.SaveBoard(str(output), board)
        if not output.exists() or output.stat().st_size < 100:
            raise RuntimeError("KiCad did not produce a valid board file.")
        return {"status": "SOURCE_GENERATED_PENDING_DRC", "passed": False, "native_files": [output.name],
                "component_count": len(components), "net_count": len(nets), "track_segment_count": len(tracks),
                "copper_layers": copper, "board_thickness_mm": thickness,
                "notice": "Editable KiCad PCB generated from explicit, provenance-labelled layout data. This executor does not autoroute, select parts, validate electrical rules or certify fabrication; KiCad DRC and engineer review are mandatory."}
    except (ValueError, RuntimeError, TypeError, KeyError) as exc:
        return {"status": "BLOCKED_OR_FAILED", "passed": False, "detail": str(exc), "missing_inputs": []}

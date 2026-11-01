from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

MAX_ENGINE_SECONDS = 180
SAFE_BOARD = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number(params: dict[str, Any], key: str) -> float | None:
    item = params.get(key)
    if isinstance(item, dict):
        if item.get("value_basis") not in ("user_specified", "source_verified", "calculated_with_method"):
            return None
        item = item.get("value")
    if isinstance(item, (int, float)) and not isinstance(item, bool) and 0 < float(item) < 10000:
        return float(item)
    return None


def _run(command: list[str], cwd: Path, timeout: int = MAX_ENGINE_SECONDS) -> dict[str, Any]:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        return {"command": command, "exit_code": result.returncode, "passed": result.returncode == 0,
                "stdout": result.stdout[-10000:], "stderr": result.stderr[-10000:]}
    except FileNotFoundError:
        return {"command": command, "passed": False, "unavailable": True, "detail": "Required native executable is not installed."}
    except subprocess.TimeoutExpired:
        return {"command": command, "passed": False, "timed_out": True, "detail": "Native engineering command timed out."}


def generate_firmware(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    spec = _dict(plan.get("firmware_design"))
    target = _dict(spec.get("target"))
    board = target.get("platformio_board")
    framework = target.get("framework", "arduino")
    platform = spec.get("platform")
    if not isinstance(board, str) or not SAFE_BOARD.fullmatch(board):
        return {"status": "BLOCKED", "passed": False, "missing_inputs": ["firmware_design.target.platformio_board: verified PlatformIO board identifier"]}
    if framework not in ("arduino", "espidf", "zephyr"):
        return {"status": "BLOCKED", "passed": False, "missing_inputs": ["supported, verified firmware framework (arduino, espidf, or zephyr)"]}
    if not isinstance(platform, str) or not SAFE_BOARD.fullmatch(platform):
        return {"status": "BLOCKED", "passed": False, "missing_inputs": ["firmware_design.platform: verified PlatformIO platform identifier"]}
    source = spec.get("application_source")
    if not isinstance(source, str) or not source.strip() or len(source) > 100000:
        return {"status": "BLOCKED", "passed": False, "missing_inputs": ["reviewed board-specific application_source; generated firmware cannot infer product behaviour safely"]}
    firmware = root / "05_Firmware"
    (firmware / "src").mkdir(parents=True, exist_ok=True)
    (firmware / "platformio.ini").write_text(
        "[env:foundry]\nplatform = " + platform +
        "\nboard = " + board + "\nframework = " + framework +
        "\nmonitor_speed = 115200\n", encoding="utf-8")
    (firmware / "src" / "main.cpp").write_text(source, encoding="utf-8")
    result = _run(["platformio", "run", "-e", "foundry"], firmware)
    result.update({"status": "COMPILED" if result["passed"] else "FAILED", "source": "05_Firmware/src/main.cpp",
                   "build_configuration": "05_Firmware/platformio.ini",
                   "missing_inputs": [] if result["passed"] else ["resolve compiler errors and rerun build"]})
    return result


def _freecad_macro(params: dict[str, float], output: Path) -> str:
    # The only dimensions entering this macro have already passed provenance checks.
    return """import FreeCAD as App
import Part
from FreeCAD import Vector
doc = App.newDocument('FoundryParametricEnclosure')
L = {length}
W = {width}
H = {height}
wall = {wall}
floor = {floor}
corner = {corner}
if wall * 2 >= min(L, W) or floor >= H or corner * 2 >= min(L, W):
    raise ValueError('Invalid enclosure parameter relationship')
outer = Part.makeBox(L, W, H)
inner = Part.makeBox(L-2*wall, W-2*wall, H-floor)
inner.translate(Vector(wall, wall, floor))
body = outer.cut(inner)
vertical = [e for e in body.Edges if abs((e.Vertexes[-1].Point-e.Vertexes[0].Point).z) > H*0.9]
if corner > 0:
    body = body.makeFillet(corner, vertical)
obj = doc.addObject('PartDesign::Feature', 'Enclosure')
obj.Label = 'Parametric enclosure - verify fit before manufacture'
obj.Shape = body
obj.addProperty('App::PropertyLength', 'Length', 'Foundry').Length = L
obj.addProperty('App::PropertyLength', 'Width', 'Foundry').Width = W
obj.addProperty('App::PropertyLength', 'Height', 'Foundry').Height = H
obj.addProperty('App::PropertyLength', 'Wall', 'Foundry').Wall = wall
obj.addProperty('App::PropertyLength', 'Floor', 'Foundry').Floor = floor
doc.recompute()
doc.saveAs(r'{fcstd}')
Part.export([obj], r'{step}')
""".format(length=params["length"], width=params["width"], height=params["height"],
           wall=params["wall"], floor=params["floor"], corner=params["corner"],
           fcstd=str(output / "foundry_enclosure.FCStd"), step=str(output / "foundry_enclosure.step"))


def generate_mechanical(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    spec = _dict(plan.get("mechanical_design"))
    raw = _dict(spec.get("parameters"))
    keys = ("length", "width", "height", "wall", "floor", "corner")
    params = {key: _number(raw, key) for key in keys}
    missing = [key for key, value in params.items() if value is None]
    provenance = {key: (raw.get(key, {}).get("value_basis") if isinstance(raw.get(key), dict) else "UNSPECIFIED") for key in keys}
    if missing:
        return {"status": "BLOCKED", "passed": False,
                "missing_inputs": ["mechanical_design.parameters." + key + " with verified/user-specified value and provenance" for key in missing],
                "provided_provenance": provenance}
    if params["wall"] * 2 >= min(params["length"], params["width"]) or params["floor"] >= params["height"]:
        return {"status": "BLOCKED", "passed": False, "missing_inputs": ["dimensionally consistent enclosure parameter relationships"]}
    out = root / "06_Mechanical_CAD"
    out.mkdir(parents=True, exist_ok=True)
    macro = out / "generate_enclosure.FCMacro"
    macro.write_text(_freecad_macro(params, out), encoding="utf-8")
    executable = shutil.which("FreeCADCmd") or shutil.which("freecadcmd")
    if not executable:
        return {"status": "SOURCE_GENERATED_TOOL_UNAVAILABLE", "passed": False,
                "macro": "06_Mechanical_CAD/generate_enclosure.FCMacro",
                "missing_inputs": ["FreeCADCmd executable in worker image"]}
    run = _run([executable, str(macro)], out)
    step = out / "foundry_enclosure.step"
    fcstd = out / "foundry_enclosure.FCStd"
    run.update({"status": "GENERATED" if run["passed"] and step.exists() and fcstd.exists() else "FAILED",
                "native_files": [p.name for p in (fcstd, step) if p.exists()],
                "macro": "06_Mechanical_CAD/generate_enclosure.FCMacro",
                "provenance": provenance,
                "missing_inputs": [] if run["passed"] and step.exists() and fcstd.exists() else ["resolve FreeCAD macro/export errors"]})
    run["passed"] = bool(run["passed"] and step.exists() and fcstd.exists())
    return run


def generate_engineering_artifacts(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Run evidence-gated native generators. Never turns missing evidence into fabricated geometry or firmware."""
    root.mkdir(parents=True, exist_ok=True)
    firmware = generate_firmware(root, plan)
    mechanical = generate_mechanical(root, plan)
    connector = generate_proprietary_connector(root, plan)
    return {"firmware": firmware, "mechanical": mechanical, "proprietary_connector": connector,
            "release_state": "READY_FOR_REVIEW" if firmware.get("passed") and mechanical.get("passed") else "ENGINEERING_INCOMPLETE",
            "notice": "Native artefacts are generated only from explicit, provenance-labelled inputs. Tool success is not safety, EMC, environmental, prototype or manufacturing certification."}


def generate_proprietary_connector(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Generate matched keyed male/female concept geometry only from provenance-labelled dimensions."""
    interface = _dict(plan.get("interface_design"))
    raw = _dict(interface.get("connector_geometry"))
    numeric = ("body_length", "body_width", "body_height", "pitch", "contact_diameter", "cavity_depth", "clearance")
    values = {key: _number(raw, key) for key in numeric}
    count = raw.get("pin_count")
    rows = raw.get("rows", 1)
    missing = [key for key, value in values.items() if value is None]
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 40:
        missing.append("pin_count (integer 1..40)")
    if not isinstance(rows, int) or rows not in (1, 2, 3, 4):
        missing.append("rows (integer 1..4)")
    if missing:
        return {"status": "BLOCKED", "passed": False,
                "missing_inputs": ["interface_design.connector_geometry." + key + " with verified/user-specified provenance" for key in missing]}
    L, W, H = values["body_length"], values["body_width"], values["body_height"]
    pitch, diameter = values["pitch"], values["contact_diameter"]
    depth, clearance = values["cavity_depth"], values["clearance"]
    if diameter >= pitch or depth >= H or clearance * 2 >= min(L, W) or rows * pitch > W:
        return {"status": "BLOCKED", "passed": False, "missing_inputs": ["physically consistent connector envelope, contact pitch and cavity parameters"]}
    out = root / "07_Proprietary_Interfaces"
    out.mkdir(parents=True, exist_ok=True)
    macro = out / "generate_mating_connector.FCMacro"
    macro.write_text("""import FreeCAD as App
import Part
from FreeCAD import Vector
doc = App.newDocument('FoundryProprietaryConnector')
L={L}; W={W}; H={H}; pitch={pitch}; d={diameter}; depth={depth}; clearance={clearance}
count={count}; rows={rows}
cols = (count + rows - 1) // rows
male = Part.makeBox(L, W, H)
female = Part.makeBox(L + 2*clearance, W + 2*clearance, H)
cavity = Part.makeBox(L + clearance, W + clearance, depth + 0.2)
cavity.translate(Vector(clearance/2, clearance/2, H-depth))
female = female.cut(cavity)
for i in range(count):
    row = i // cols
    col = i % cols
    x = (L - (cols-1)*pitch)/2 + col*pitch
    y = (W - (rows-1)*pitch)/2 + row*pitch
    pin = Part.makeCylinder(d/2, depth, Vector(x, y, H-depth))
    male = male.fuse(pin)
    bore = Part.makeCylinder(d/2 + clearance/2, depth+0.2, Vector(x+clearance/2, y+clearance/2, H-depth))
    female = female.cut(bore)
# Polarising rail and mating channel; dimensions remain part of the envelope, not electrical safety evidence.
rail = Part.makeBox(L*0.45, max(clearance, 0.3), H*0.15)
rail.translate(Vector(L*0.275, W-max(clearance,0.3), H*0.85))
male = male.fuse(rail)
slot = Part.makeBox(L*0.45+clearance, max(clearance*2,0.6), H*0.15+clearance)
slot.translate(Vector(L*0.275-clearance/2, W+clearance-max(clearance*2,0.6), H*0.85-clearance/2))
female = female.cut(slot)
a=doc.addObject('PartDesign::Feature','MalePlug'); a.Shape=male
b=doc.addObject('PartDesign::Feature','FemaleSocket'); b.Shape=female
doc.recompute()
doc.saveAs(r'{fcstd}')
Part.export([a], r'{male}')
Part.export([b], r'{female}')
""".format(L=L, W=W, H=H, pitch=pitch, diameter=diameter, depth=depth, clearance=clearance,
           count=count, rows=rows, fcstd=str(out / "foundry_connector_pair.FCStd"),
           male=str(out / "foundry_connector_male.step"), female=str(out / "foundry_connector_female.step")), encoding="utf-8")
    executable = shutil.which("FreeCADCmd") or shutil.which("freecadcmd")
    if not executable:
        return {"status": "SOURCE_GENERATED_TOOL_UNAVAILABLE", "passed": False,
                "macro": "07_Proprietary_Interfaces/generate_mating_connector.FCMacro",
                "missing_inputs": ["FreeCADCmd executable in worker image"]}
    run = _run([executable, str(macro)], out)
    expected = [out / "foundry_connector_pair.FCStd", out / "foundry_connector_male.step", out / "foundry_connector_female.step"]
    run.update({"status": "GENERATED" if run["passed"] and all(p.exists() for p in expected) else "FAILED",
                "native_files": [str(p.relative_to(root)) for p in expected if p.exists()],
                "note": "Geometric mating concept only. Contact assignments, current/voltage ratings, plating, insulation, retention force, tolerance stack, ingress protection and cycle life require separate engineering evidence and prototype validation."})
    run["passed"] = bool(run["passed"] and all(p.exists() for p in expected))
    return run

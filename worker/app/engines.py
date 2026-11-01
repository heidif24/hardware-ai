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
    if not isinstance(board, str) or not SAFE_BOARD.fullmatch(board):
        return {"status": "BLOCKED", "passed": False, "missing_inputs": ["firmware_design.target.platformio_board: verified PlatformIO board identifier"]}
    if framework not in ("arduino", "espidf", "zephyr"):
        return {"status": "BLOCKED", "passed": False, "missing_inputs": ["supported, verified firmware framework (arduino, espidf, or zephyr)"]}
    source = spec.get("application_source")
    if not isinstance(source, str) or not source.strip():
        return {"status": "BLOCKED", "passed": False, "missing_inputs": ["reviewed board-specific application_source; generated firmware cannot infer product behaviour safely"]}
    firmware = root / "05_Firmware"
    (firmware / "src").mkdir(parents=True, exist_ok=True)
    (firmware / "platformio.ini").write_text(
        "[env:foundry]\nplatform = " + str(spec.get("platform", "espressif32")) +
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
try:
    vertical = [e for e in body.Edges if abs((e.Vertexes[-1].Point-e.Vertexes[0].Point).z) > H*0.9]
    body = body.makeFillet(corner, vertical)
except Exception:
    pass
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
    return {"firmware": firmware, "mechanical": mechanical,
            "release_state": "READY_FOR_REVIEW" if firmware.get("passed") and mechanical.get("passed") else "ENGINEERING_INCOMPLETE",
            "notice": "Native artefacts are generated only from explicit, provenance-labelled inputs. Tool success is not safety, EMC, environmental, prototype or manufacturing certification."}

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from .innovation import build_innovation_dossier

APP_VERSION = "0.1.0"
JOBS_ROOT = Path(os.getenv("JOBS_ROOT", ".data/jobs"))
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_COMMAND_SECONDS = 120
API_TOKEN = os.getenv("WORKER_API_TOKEN", "")
JOBS_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Hardware Foundry Engineering Worker", version=APP_VERSION)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_token(authorization: str | None) -> None:
    if not API_TOKEN:
        raise HTTPException(status_code=503, detail="Engineering worker is not configured: WORKER_API_TOKEN is missing.")
    supplied = authorization or ""
    expected = "Bearer " + API_TOKEN
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid worker credentials.")


class JobRequest(BaseModel):
    project_name: str = Field(min_length=1, max_length=180)
    brief: dict[str, Any]
    design: dict[str, Any]
    engineering_plan: dict[str, Any]
    decision_selections: dict[str, str]
    decision_notes: dict[str, str] = Field(default_factory=dict)
    global_notes: str = ""
    design_approved: bool
    files: dict[str, str] = Field(default_factory=dict)


def job_dir(job_id: str) -> Path:
    try:
        parsed = uuid.UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Engineering job not found.") from exc
    return JOBS_ROOT / str(parsed)


def read_job(path: Path) -> dict[str, Any]:
    file = path / "job.json"
    if not file.exists():
        raise HTTPException(status_code=404, detail="Engineering job not found.")
    return json.loads(file.read_text(encoding="utf-8"))


def write_job(path: Path, job: dict[str, Any]) -> None:
    temp = path / "job.json.tmp"
    temp.write_text(json.dumps(job, indent=2), encoding="utf-8")
    temp.replace(path / "job.json")


def run_command(command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=MAX_COMMAND_SECONDS, check=False)
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout[-12000:],
            "stderr": result.stderr[-12000:],
            "passed": result.returncode == 0,
        }
    except FileNotFoundError:
        return {"command": command, "passed": False, "unavailable": True, "detail": "Executable not installed."}
    except subprocess.TimeoutExpired:
        return {"command": command, "passed": False, "timed_out": True, "detail": "Command exceeded the execution time limit."}


def probe_toolchains() -> dict[str, Any]:
    probes = {
        "kicad_cli": ["kicad-cli", "version"],
        "freecad": ["FreeCADCmd", "--version"],
        "arm_none_eabi_gcc": ["arm-none-eabi-gcc", "--version"],
        "avr_gcc": ["avr-gcc", "--version"],
        "cmake": ["cmake", "--version"],
        "platformio": ["platformio", "--version"],
    }
    inventory: dict[str, Any] = {}
    for name, command in probes.items():
        result = run_command(command)
        output = (result.get("stdout") or result.get("stderr") or "").splitlines()
        inventory[name] = {
            "available": result.get("passed", False),
            "version": output[0][:180] if output else None,
            "detail": result.get("detail"),
        }
    return inventory


def write_user_files(root: Path, encoded_files: dict[str, str]) -> list[str]:
    written: list[str] = []
    total = 0
    for raw_name, encoded in encoded_files.items():
        relative = PurePosixPath(raw_name)
        if relative.is_absolute() or not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
            raise ValueError("Unsafe artifact path: " + raw_name)
        if len(relative.parts) > 6 or len(raw_name) > 240:
            raise ValueError("Artifact path is too deep or too long.")
        data = base64.b64decode(encoded, validate=True)
        total += len(data)
        if total > MAX_UPLOAD_BYTES:
            raise ValueError("Uploaded engineering files exceed the 50 MB job limit.")
        destination = root.joinpath(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        written.append(relative.as_posix())
    return written


def validate_kicad(root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for schematic in root.rglob("*.kicad_sch"):
        report = schematic.with_suffix(".erc.txt")
        results.append(run_command(["kicad-cli", "sch", "erc", "--output", str(report), "--format", "report", str(schematic)], cwd=root))
    for board in root.rglob("*.kicad_pcb"):
        report = board.with_suffix(".drc.txt")
        drc = run_command(["kicad-cli", "pcb", "drc", "--output", str(report), "--format", "report", str(board)], cwd=root)
        results.append(drc)
        if drc.get("passed"):
            gerber_dir = board.parent / "gerbers"
            drill_dir = board.parent / "drill"
            gerber_dir.mkdir(exist_ok=True)
            drill_dir.mkdir(exist_ok=True)
            results.append(run_command(["kicad-cli", "pcb", "export", "gerbers", "--output", str(gerber_dir) + "/", str(board)], cwd=root))
            results.append(run_command(["kicad-cli", "pcb", "export", "drill", "--output", str(drill_dir) + "/", str(board)], cwd=root))
    return results


def generate_native_project_scaffold(root: Path, job: dict[str, Any]) -> list[dict[str, Any]]:
    """Create a self-contained engineering workspace contract for downstream generators."""
    design = job.get("design", {})
    plan = job.get("engineering_plan", {})
    architecture = root / "00_Foundry_Generation"
    architecture.mkdir(parents=True, exist_ok=True)
    manifest = {
        "project": job.get("project_name"),
        "design": design,
        "decisions": job.get("decision_selections", {}),
        "stages": ["electronics", "pcb", "firmware", "mechanical", "validation"],
        "native_engines": {
            "electronics": "KiCad CLI",
            "pcb": "KiCad CLI",
            "firmware": "PlatformIO / installed GCC toolchains",
            "mechanical": "FreeCADCmd",
        },
        "release_boundary": "Generation scaffolds are not fabrication approval; each native artifact must pass applicable validation.",
    }
    (architecture / "generation_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (architecture / "ai_engineering_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    gates = plan.get("generation_gates", {}) if isinstance(plan, dict) else {}
    blocked = [name for name, gate in gates.items() if not isinstance(gate, dict) or gate.get("status") != "READY"]
    return [{"passed": not blocked, "status": "READY_FOR_NATIVE_GENERATION" if not blocked else "GENERATION_BLOCKED_PENDING_ENGINEERING_INPUTS", "blocked_stages": blocked, "files": ["00_Foundry_Generation/generation_manifest.json", "00_Foundry_Generation/ai_engineering_plan.json"], "note": "No native generator may run for a blocked stage. Missing evidence is recorded rather than guessed."}]


def validate_firmware(root: Path) -> list[dict[str, Any]]:
    sources = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in (".c", ".cpp", ".ino")]
    if not sources:
        return []
    return [{
        "passed": False,
        "not_run": True,
        "source_files": [str(path.relative_to(root)) for path in sources[:40]],
        "detail": "Firmware compilation is not run until the MCU, build flags, trusted build definition and required SDK are frozen. User-supplied Makefiles are never executed by this worker.",
    }]


def inspect_mechanical_files(root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step_file in root.rglob("*.step"):
        header = step_file.read_bytes()[:256]
        valid = b"ISO-10303-21" in header
        results.append({"file": str(step_file.relative_to(root)), "format_header_valid": valid, "passed": valid, "note": "STEP header inspection only; geometry, dimensions and manufacturability are not certified."})
    for step_file in root.rglob("*.stp"):
        header = step_file.read_bytes()[:256]
        valid = b"ISO-10303-21" in header
        results.append({"file": str(step_file.relative_to(root)), "format_header_valid": valid, "passed": valid, "note": "STEP header inspection only; geometry, dimensions and manufacturability are not certified."})
    return results


def build_report(job: dict[str, Any], toolchains: dict[str, Any], uploaded: list[str], checks: dict[str, list[dict[str, Any]]]) -> str:
    missing = []
    if not any(name.endswith(".kicad_sch") for name in uploaded):
        missing.append("KiCad schematic source (.kicad_sch)")
    if not any(name.endswith(".kicad_pcb") for name in uploaded):
        missing.append("KiCad PCB source (.kicad_pcb)")
    if not any(name.lower().endswith((".step", ".stp")) for name in uploaded):
        missing.append("Dimensionally controlled mechanical STEP model")
    if not any("firmware" in name.lower() and name.lower().endswith(("makefile", ".c", ".cpp", ".ino")) for name in uploaded):
        missing.append("Board-specific firmware source and build definition")
    failed = [item for group in checks.values() for item in group if not item.get("passed")]
    status = "BLOCKED" if missing or failed else "SUCCEEDED"
    lines = [
        "# Hardware Foundry engineering execution report",
        "",
        "**Job:** " + job["id"],
        "**Project:** " + job["project_name"],
        "**Generated:** " + utc_now(),
        "**Execution status:** " + status,
        "",
        "## Approved design basis",
        "The user approved the product design basis before this job was submitted. This approval is not engineering sign-off or fabrication authorisation.",
        "",
        "## AI engineering plan and generation gates",
        "The AI plan is a structured proposal. The worker does not accept a model-generated READY label as proof of engineering evidence.",
    ]
    plan = job.get("engineering_plan", {})
    for stage, gate in (plan.get("generation_gates", {}) if isinstance(plan, dict) else {}).items():
        lines.append("- **" + str(stage) + ":** " + str(gate.get("status", "BLOCKED")) + " — " + "; ".join(map(str, gate.get("missing_inputs", []))))
    lines.extend([
        "",
        "## Uploaded source files",
        *(["- " + name for name in uploaded] or ["- No native engineering source files supplied."]),
        "",
        "## Toolchain inventory",
    ])
    for name, value in toolchains.items():
        lines.append("- **" + name + ":** " + ("available" if value["available"] else "unavailable") + ((" — " + str(value["version"])) if value.get("version") else ""))
    lines.extend(["", "## Validation execution"])
    for group, entries in checks.items():
        lines.append("### " + group)
        if not entries:
            lines.append("- Not run: no applicable native source file was supplied.")
        for entry in entries:
            lines.append("- " + ("PASS" if entry.get("passed") else "FAIL / NOT AVAILABLE") + " — " + json.dumps(entry, ensure_ascii=False)[:900])
    lines.extend(["", "## Missing engineering inputs"])
    lines.extend(["- " + item for item in missing] or ["- No missing source category was detected by this initial worker check."])
    lines.extend([
        "",
        "## Release boundary",
        "This worker executes available checks against actual supplied source files. It does not invent component identities, electrical ratings, pin maps, CAD dimensions or test evidence. A successful tool invocation is not equivalent to design approval, regulatory certification, prototype validation or factory acceptance.",
        "",
        "**Package state:** " + ("ENGINEERING_WORK_INCOMPLETE" if status == "BLOCKED" else "TOOLCHAIN_CHECKS_PASSED_PENDING_ENGINEERING_SIGN_OFF"),
    ])
    return "\n".join(lines) + "\n"


def execute_job(path: Path) -> None:
    job = read_job(path)
    job["status"] = "RUNNING"
    job["started_at"] = utc_now()
    write_job(path, job)
    try:
        toolchains = probe_toolchains()
        uploaded = job.get("uploaded_files", [])
        workspace_generation = generate_native_project_scaffold(path / "workspace", job)
        innovation = build_innovation_dossier(path / "workspace", job.get("design", {}), job.get("decision_selections", {}), job.get("global_notes", ""))
        electronics = validate_kicad(path / "workspace")
        firmware = validate_firmware(path / "workspace")
        mechanical = inspect_mechanical_files(path / "workspace")
        checks = {"Engineering workspace": workspace_generation, "Generative innovation": innovation, "KiCad": electronics, "Firmware": firmware, "Mechanical": mechanical}
        report = build_report(job, toolchains, uploaded, checks)
        (path / "workspace" / "09_Testing_And_Validation").mkdir(parents=True, exist_ok=True)
        (path / "workspace" / "09_Testing_And_Validation" / "engineering_execution_report.md").write_text(report, encoding="utf-8")
        result = {
            "toolchains": toolchains,
            "checks": checks,
            "innovation": innovation,
            "uploaded_files": uploaded,
            "status": "BLOCKED" if "ENGINEERING_WORK_INCOMPLETE" in report else "SUCCEEDED",
        }
        (path / "execution_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        archive = path / "engineering_execution_bundle.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for file in (path / "workspace").rglob("*"):
                if file.is_file():
                    bundle.write(file, file.relative_to(path / "workspace").as_posix())
            bundle.write(path / "design_basis.json", "01_Product_Definition/approved_design_basis.json")
            bundle.write(path / "execution_result.json", "09_Testing_And_Validation/execution_result.json")
        job["status"] = result["status"]
        job["result"] = result
        job["artifact"] = "engineering_execution_bundle.zip"
        job["finished_at"] = utc_now()
        write_job(path, job)
    except Exception as exc:
        job["status"] = "FAILED"
        job["error"] = str(exc)[:2000]
        job["finished_at"] = utc_now()
        write_job(path, job)


@app.on_event("startup")
async def recover_interrupted_jobs() -> None:
    for file in JOBS_ROOT.glob("*/job.json"):
        try:
            job = json.loads(file.read_text(encoding="utf-8"))
            if job.get("status") in ("QUEUED", "RUNNING"):
                job["status"] = "FAILED"
                job["error"] = "Worker restarted before this job completed. Resubmit the job to retry."
                job["finished_at"] = utc_now()
                write_job(file.parent, job)
        except Exception:
            continue


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "hardware-foundry-engineering-worker", "version": APP_VERSION}


@app.get("/v1/toolchains")
async def toolchains(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_token(authorization)
    return probe_toolchains()


@app.post("/v1/jobs", status_code=202)
async def create_job(payload: JobRequest, background: BackgroundTasks, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_token(authorization)
    if payload.design_approved is not True:
        raise HTTPException(status_code=409, detail="The design basis must be approved before engineering execution.")
    if not isinstance(payload.design.get("modules"), list) or not payload.design.get("modules"):
        raise HTTPException(status_code=422, detail="A generated functional architecture is required.")
    if not isinstance(payload.engineering_plan.get("generation_gates"), dict):
        raise HTTPException(status_code=422, detail="A gated AI engineering plan is required.")
    decisions = payload.design.get("decision_points") or []
    unresolved = [item.get("title", item.get("id", "Decision")) for item in decisions if not payload.decision_selections.get(item.get("id"))]
    if unresolved:
        raise HTTPException(status_code=422, detail="Unselected design decisions: " + ", ".join(unresolved))
    now = datetime.now(timezone.utc).timestamp()
    active = 0
    recent = 0
    for record in JOBS_ROOT.glob("*/job.json"):
        try:
            existing = json.loads(record.read_text(encoding="utf-8"))
            if existing.get("status") in ("QUEUED", "RUNNING"):
                active += 1
            created = datetime.fromisoformat(existing.get("created_at", "")).timestamp()
            if now - created < 86400:
                recent += 1
        except Exception:
            continue
    if active >= 2:
        raise HTTPException(status_code=429, detail="The engineering worker is at its two-job concurrency limit. Check an existing job before submitting another.")
    if recent >= 20:
        raise HTTPException(status_code=429, detail="The engineering worker has reached its daily job quota. Try again later.")
    job_id = str(uuid.uuid4())
    path = JOBS_ROOT / job_id
    workspace = path / "workspace"
    workspace.mkdir(parents=True, exist_ok=False)
    try:
        uploaded = write_user_files(workspace, payload.files)
    except Exception as exc:
        shutil.rmtree(path, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    basis = {
        "project_name": payload.project_name,
        "brief": payload.brief,
        "design": payload.design,
        "engineering_plan": payload.engineering_plan,
        "decision_selections": payload.decision_selections,
        "decision_notes": payload.decision_notes,
        "global_notes": payload.global_notes,
    }
    basis_hash = hashlib.sha256(json.dumps(basis, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    job = {
        "id": job_id,
        "project_name": payload.project_name,
        "design": payload.design,
        "engineering_plan": payload.engineering_plan,
        "decision_selections": payload.decision_selections,
        "global_notes": payload.global_notes,
        "status": "QUEUED",
        "created_at": utc_now(),
        "design_basis_sha256": basis_hash,
        "uploaded_files": uploaded,
    }
    write_job(path, job)
    (path / "design_basis.json").write_text(json.dumps(basis, indent=2), encoding="utf-8")
    background.add_task(execute_job, path)
    return {"job_id": job_id, "status": "QUEUED", "design_basis_sha256": basis_hash, "status_url": "/v1/jobs/" + job_id, "artifact_url": "/v1/jobs/" + job_id + "/artifact"}


@app.get("/v1/jobs/{job_id}")
async def get_job(job_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    require_token(authorization)
    path = job_dir(job_id)
    job = read_job(path)
    return {key: value for key, value in job.items() if key != "uploaded_files"}


@app.get("/v1/jobs/{job_id}/artifact")
async def get_artifact(job_id: str, authorization: str | None = Header(default=None)) -> FileResponse:
    require_token(authorization)
    path = job_dir(job_id)
    job = read_job(path)
    if job.get("status") not in ("BLOCKED", "SUCCEEDED"):
        raise HTTPException(status_code=409, detail="The engineering execution bundle is not ready yet.")
    archive = path / "engineering_execution_bundle.zip"
    if not archive.exists():
        raise HTTPException(status_code=404, detail="Engineering execution bundle not found.")
    return FileResponse(archive, media_type="application/zip", filename="Hardware_Foundry_Execution_" + job_id[:8] + ".zip")

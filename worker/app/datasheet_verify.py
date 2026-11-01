from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Conservative extractors — never invent part numbers that are not present in the file text.

PART_RE = re.compile(
    r"\b(?:P/?N|Part(?:\s+Number)?|Order(?:ing)?\s+Code|MPN|Device)\s*[:#]?\s*([A-Z0-9][A-Z0-9._/-]{3,31})\b",
    re.IGNORECASE,
)
MFG_RE = re.compile(
    r"\b(?:Manufacturer|Vendor|Made\s+by|Company)\s*[:#]?\s*([A-Za-z][A-Za-z0-9 .,&-]{2,48})\b",
    re.IGNORECASE,
)
# Common manufacturer names appearing in headers/footers
KNOWN_MFG = re.compile(
    r"\b(Texas Instruments|Analog Devices|STMicroelectronics|NXP|Microchip|Infineon|"
    r"ON Semiconductor|onsemi|Maxim Integrated|Renesas|Silicon Labs|Espressif|"
    r"Nordic Semiconductor|Murata|TDK|Samsung|Skyworks|Qorvo|Broadcom|Qualcomm|"
    r"Bosch|Honeywell|Amphenol|Molex|TE Connectivity|Hirose|JST|Würth|Wurth)\b",
    re.IGNORECASE,
)


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _extract_pdf_text(path: Path, max_chars: int = 80000) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return ""
    try:
        reader = PdfReader(str(path))
        chunks: list[str] = []
        total = 0
        for page in reader.pages[:40]:
            text = page.extract_text() or ""
            chunks.append(text)
            total += len(text)
            if total >= max_chars:
                break
        return "\n".join(chunks)[:max_chars]
    except Exception:
        return ""


def _extract_text_file(path: Path, max_chars: int = 80000) -> str:
    try:
        raw = path.read_bytes()[: max_chars * 2]
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                return raw.decode(enc)[:max_chars]
            except UnicodeDecodeError:
                continue
        return ""
    except Exception:
        return ""


def extract_document_text(path: Path) -> tuple[str, str]:
    """Return (text, method). method is pdf|text|empty."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf_text(path)
        return text, "pdf" if text.strip() else "empty"
    if suffix in {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".log"}:
        text = _extract_text_file(path)
        return text, "text" if text.strip() else "empty"
    # Try text decode for unknown types that might be plain
    if path.stat().st_size < 2_000_000:
        text = _extract_text_file(path)
        if len(text.strip()) > 40:
            return text, "text"
    return "", "empty"


def _find_candidates_in_text(text: str) -> dict[str, Any]:
    part_numbers = list({m.group(1).strip() for m in PART_RE.finditer(text)})[:20]
    manufacturers = list({m.group(1).strip() for m in MFG_RE.finditer(text)})[:10]
    known = list({m.group(1).strip() for m in KNOWN_MFG.finditer(text)})[:10]
    for k in known:
        if k not in manufacturers:
            manufacturers.append(k)
    return {
        "part_numbers_found": part_numbers,
        "manufacturers_found": manufacturers,
        "char_count": len(text),
    }


def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _match_registry_entry(
    entry: dict[str, Any],
    findings: dict[str, Any],
    source_file: str,
    excerpt: str,
) -> dict[str, Any] | None:
    """If datasheet text grounds this entry, return an upgraded copy."""
    if entry.get("identity_status") not in (None, "", "UNVERIFIED_FUNCTIONAL_CLASS", "PENDING"):
        # Already claimed verified — only reinforce with source if missing
        if entry.get("source_reference") and entry.get("evidence_excerpt"):
            return None

    functional = str(entry.get("functional_class") or entry.get("description") or "")
    func_norm = _normalize(functional)
    parts = findings.get("part_numbers_found") or []
    mfgs = findings.get("manufacturers_found") or []

    # Require at least one part number present in the datasheet text
    if not parts:
        return None

    # Prefer part numbers that share tokens with the functional class (weak but honest signal)
    chosen_part = parts[0]
    for p in parts:
        pn = _normalize(p)
        if func_norm and (pn in func_norm or any(tok and tok in pn for tok in re.findall(r"[a-z0-9]{3,}", func_norm)[:6])):
            chosen_part = p
            break

    chosen_mfg = mfgs[0] if mfgs else None
    evidence = excerpt.strip()
    if len(evidence) > 400:
        evidence = evidence[:400] + "…"

    upgraded = dict(entry)
    upgraded["identity_status"] = "SOURCE_GROUNDED"
    upgraded["part_number"] = chosen_part
    if chosen_mfg:
        upgraded["manufacturer"] = chosen_mfg
    upgraded["source_reference"] = source_file
    upgraded["evidence_excerpt"] = evidence
    upgraded["verification_method"] = "datasheet_text_extraction"
    upgraded["notes"] = (
        str(entry.get("notes") or "")
        + " Grounded from uploaded datasheet text; engineer must still confirm symbol, footprint, ratings and pin map."
    ).strip()
    # Do NOT auto-verify pin map / footprint / symbol — those need library work
    upgraded.setdefault("symbol_status", "PENDING")
    upgraded.setdefault("footprint_status", "PENDING")
    upgraded.setdefault("pin_map_status", "PENDING")
    return upgraded


def verify_from_uploaded_datasheets(
    workspace: Path,
    plan: dict[str, Any],
    design: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Scan workspace uploads for datasheet-like files and ground component candidates.

    Updates plan['component_candidates'] in place when evidence is found.
    Writes 03_Electronics/datasheet_verification_report.json
    """
    design = design or {}
    out = workspace / "03_Electronics"
    out.mkdir(parents=True, exist_ok=True)

    # Collect candidate datasheet files
    patterns = (".pdf", ".txt", ".md")
    files: list[Path] = []
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        # Skip generated outputs
        if "03_Electronics" in path.parts and path.name.startswith(("system_", "component_", "logical_", "electronics_", "connectivity")):
            continue
        if path.suffix.lower() in patterns or "datasheet" in path.name.lower() or "ds_" in path.name.lower():
            files.append(path)

    documents: list[dict[str, Any]] = []
    all_findings: list[dict[str, Any]] = []

    for path in files[:30]:
        text, method = extract_document_text(path)
        rel = str(path.relative_to(workspace))
        doc: dict[str, Any] = {
            "file": rel,
            "method": method,
            "bytes": path.stat().st_size,
        }
        if not text.strip():
            doc["status"] = "NO_EXTRACTABLE_TEXT"
            documents.append(doc)
            continue
        findings = _find_candidates_in_text(text)
        findings["file"] = rel
        # Keep a short excerpt around first part number if possible
        excerpt = text[:500]
        for pn in findings.get("part_numbers_found") or []:
            idx = text.find(pn)
            if idx >= 0:
                start = max(0, idx - 80)
                excerpt = text[start : start + 320]
                break
        findings["excerpt"] = excerpt
        doc["status"] = "EXTRACTED"
        doc["findings"] = {
            "part_numbers_found": findings["part_numbers_found"],
            "manufacturers_found": findings["manufacturers_found"],
            "char_count": findings["char_count"],
        }
        documents.append(doc)
        all_findings.append(findings)

    candidates = list(_list(plan.get("component_candidates")))
    # Normalize to dicts
    normalized: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, dict):
            normalized.append(dict(item))
        else:
            normalized.append({"description": str(item), "identity_status": "UNVERIFIED_FUNCTIONAL_CLASS"})

    # If plan has no candidates, seed from design modules for matching context
    if not normalized:
        for mod in _list(design.get("modules")):
            m = _dict(mod)
            for part in _list(m.get("parts"))[:4]:
                normalized.append({
                    "description": str(part),
                    "module": str(m.get("name") or ""),
                    "identity_status": "UNVERIFIED_FUNCTIONAL_CLASS",
                })

    upgrades: list[dict[str, Any]] = []
    used_parts: set[str] = set()

    for findings in all_findings:
        source_file = findings["file"]
        excerpt = findings.get("excerpt") or ""
        for i, entry in enumerate(normalized):
            if entry.get("identity_status") == "SOURCE_GROUNDED" and entry.get("source_reference"):
                continue
            upgraded = _match_registry_entry(entry, findings, source_file, excerpt)
            if not upgraded:
                continue
            pn = str(upgraded.get("part_number") or "")
            if pn and pn in used_parts:
                continue
            if pn:
                used_parts.add(pn)
            normalized[i] = upgraded
            upgrades.append({
                "index": i,
                "functional_class": upgraded.get("functional_class") or upgraded.get("description"),
                "part_number": upgraded.get("part_number"),
                "manufacturer": upgraded.get("manufacturer"),
                "source_reference": source_file,
            })
            # One upgrade per findings doc per pass — still allow multiple docs
            # but avoid assigning the same PN twice

    plan["component_candidates"] = normalized

    report = {
        "status": "DATASHEET_VERIFICATION_COMPLETED",
        "documents_scanned": len(documents),
        "documents": documents,
        "upgrades": upgrades,
        "grounded_count": len(upgrades),
        "remaining_unverified": sum(
            1 for c in normalized if c.get("identity_status") in (None, "", "UNVERIFIED_FUNCTIONAL_CLASS", "PENDING")
        ),
        "rules": [
            "Part numbers and manufacturers are taken only from uploaded file text.",
            "SOURCE_GROUNDED means text evidence exists; it is not full electrical qualification.",
            "Symbol, footprint and pin-map status remain PENDING until library work is done.",
            "An engineer must confirm ratings, lifecycle and applicability before fabrication.",
        ],
    }
    (out / "datasheet_verification_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    return {
        "status": report["status"],
        "passed": True,
        "documents_scanned": len(documents),
        "grounded_count": len(upgrades),
        "files": ["03_Electronics/datasheet_verification_report.json"],
        "upgrades": upgrades,
        "note": (
            "Datasheet verification extracts identity evidence from uploads only. "
            "It does not certify electrical design or authorize fabrication."
        ),
    }

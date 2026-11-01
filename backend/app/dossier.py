import csv, io, json, re, zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")[:70] or "hardware_product"

def build_dossier(payload: dict) -> tuple[bytes, str]:
    design = payload.get("design")
    if not isinstance(design, dict) or not design.get("modules"):
        raise ValueError("Generate a product architecture before exporting its dossier.")
    brief = str(payload.get("idea") or "").strip()
    if len(brief) < 8:
        raise ValueError("A complete product brief is required.")
    product = str(design.get("product_name") or "Hardware product")
    modules = design.get("modules", [])
    manifest = {
        "package_type": "vendor_neutral_engineering_dossier",
        "product_name": product, "revision": "A",
        "status": "ENGINEERING_DOSSIER_NOT_FABRICATION_RELEASE",
        "contains_fabrication_outputs": False,
        "missing_fabrication_outputs": [
            "Gerber X2", "NC drill", "IPC-356 netlist", "KiCad PCB source",
            "verified footprints", "centroid / pick-and-place", "assembly drawings", "STEP enclosure CAD"
        ],
        "reason": "These require product-specific electrical and mechanical engineering, CAD capture, ERC/DRC and engineer approval. They are not inferred from a functional concept.",
        "vendor_pricing_or_procurement_data": False,
        "created_utc": datetime.now(timezone.utc).isoformat()
    }
    bom = io.StringIO()
    writer = csv.writer(bom)
    writer.writerow(["Reference", "Functional block", "Candidate component class", "Manufacturer part number", "Datasheet", "Verification status"])
    for i, module in enumerate(modules, 1):
        for j, part in enumerate(module.get("parts", []), 1):
            writer.writerow([f"U{i}_{j}", module.get("name", ""), part, "NOT_SELECTED", "NOT_ATTACHED", "UNVERIFIED_FUNCTIONAL_CANDIDATE"])
    checklist = io.StringIO()
    check = csv.writer(checklist)
    check.writerow(["Engineering gate", "Required evidence", "Current status"])
    gates = [
        ("Requirements baseline", "Use case, environment, dimensions, interfaces, power budget and target-market constraints", "REVIEW_REQUIRED"),
        ("Electrical architecture", "Power tree, signals, interface definitions and circuit-level design", "CONCEPT_ONLY"),
        ("Component engineering", "Exact manufacturer part numbers, datasheets, lifecycle and approved alternates", "NOT_COMPLETED"),
        ("Schematic capture", "Native editable schematic and annotated netlist", "NOT_COMPLETED"),
        ("Footprint approval", "Datasheet-verified footprints and 3D package models", "NOT_COMPLETED"),
        ("PCB engineering", "Board outline, stack-up, routing, copper and clearance design", "NOT_COMPLETED"),
        ("ERC / DRC", "Electrical and design-rule reports with critical errors resolved", "NOT_COMPLETED"),
        ("Fabrication data", "Gerber X2, NC drill, IPC netlist and fabrication drawing", "NOT_COMPLETED"),
        ("Assembly data", "Approved BOM, centroid, assembly drawings and programming data", "NOT_COMPLETED"),
        ("Mechanical CAD", "Dimensioned enclosure model and STEP export", "NOT_COMPLETED"),
        ("Prototype validation", "Bring-up, functional, thermal, EMC and environmental evidence", "NOT_COMPLETED"),
        ("Engineering release", "Named engineer approval and revision-controlled release", "NOT_COMPLETED")
    ]
    for gate in gates:
        check.writerow(gate)
    height = 210 + len(modules) * 125
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}"><rect width="100%" height="100%" fill="#0b1112"/>',
           '<text x="70" y="55" fill="#b7f36b" font-size="14" font-family="Arial">HARDWARE FOUNDRY / SYSTEM ARCHITECTURE</text>',
           f'<text x="70" y="105" fill="white" font-size="30" font-family="Arial">{escape(product)}</text>']
    for i, module in enumerate(modules):
        y = 150 + i * 125
        svg.append(f'<rect x="70" y="{y}" width="1060" height="92" rx="12" fill="#151e20" stroke="#5b7550"/>')
        svg.append(f'<text x="100" y="{y+36}" fill="#b7f36b" font-size="21" font-family="Arial">{escape(str(module.get("name", "Module")))}</text>')
        svg.append(f'<text x="100" y="{y+67}" fill="#d5ded8" font-size="15" font-family="Arial">{escape(str(module.get("purpose", ""))[:150])}</text>')
    svg.append("</svg>")
    report = [f"# Engineering design report\n\n## Product\n{product}\n\n## Summary\n{design.get('summary', '')}\n"]
    for module in modules:
        report.append(f"\n## {module.get('name', 'Module')}\n{module.get('purpose', '')}\n\nInterfaces: {', '.join(module.get('interfaces', []))}\n\nCandidate component classes:\n")
        report.extend(f"- {part}\n" for part in module.get("parts", []))
    report.append("\n## Assumptions\n")
    report.extend(f"- {item}\n" for item in design.get("assumptions", []))
    report.append("\n## Risks\n")
    report.extend(f"- {item}\n" for item in design.get("risks", []))
    report.append("\n## Validation\nConcept-level only. This is not an approved circuit design.\n")
    mechanical = f"""# Mechanical design brief

Product: {product}

Before mechanical CAD release, confirm overall dimensions and tolerances; mounting points; service access; connector clearances; material and finish; manufacturing process; ingress protection; thermal dissipation; drop, vibration and impact requirements; regulatory markings; and serviceability.

No dimensionally accurate STEP/STL model is generated by this concept dossier.
"""
    handoff = f"""# Vendor-neutral manufacturing hand-off

Product: {product}
Revision: A
Requested quantity: {payload.get("quantity", 100)}

This dossier is intended to be shared only after the recipient has signed your NDA. It contains no supplier pricing, supplier selection, procurement recommendation or factory order.

For a formal manufacturing quotation, the engineering release must include native schematic, PCB source, Gerbers, NC drill, IPC netlist, approved BOM, centroid, assembly drawings, mechanical STEP files, test plan and revision record.
"""
    nda = """# MUTUAL NON-DISCLOSURE AGREEMENT — DISCUSSION TEMPLATE

This is a starting template, not legal advice. Have qualified counsel adapt it to the parties and governing law before signature.

Disclosing Party: ____________________    Receiving Party: ____________________
Effective Date: ____________________

1. Purpose. The parties may disclose product concepts, specifications, drawings, electronic designs, software, bills of materials, prototypes and related information solely to evaluate and, if separately agreed in writing, quote or manufacture the identified product.
2. Confidential information. Confidential information includes information disclosed in documents, files, demonstrations, samples, discussions or electronic form where its confidential nature is reasonably apparent.
3. Obligations. The receiving party shall use the information only for the stated purpose, protect it using reasonable safeguards, restrict access to personnel who need it and are bound by confidentiality obligations, and not disclose it to third parties without prior written consent.
4. Restrictions. The receiving party shall not commercialise, publish, register intellectual-property rights in, or use the information to develop competing products except as expressly authorised in writing.
5. Exclusions. Confidential information excludes information demonstrably public without breach, already lawfully known, independently developed without use of the disclosed information, or lawfully received from a third party without a confidentiality duty.
6. Compelled disclosure. Where legally permitted, the receiving party shall give prompt notice and disclose only what is legally required.
7. No licence or obligation. No intellectual-property licence or obligation to proceed with a transaction is granted.
8. Return or destruction. On written request, confidential materials shall be returned or securely destroyed, subject to legally required archival copies.
9. Term. Confidentiality obligations continue for ____ years from disclosure; trade secrets remain protected while they qualify as trade secrets under applicable law.
10. Governing law and disputes. Governing law: ____________________. Dispute forum: ____________________.

DISCLOSING PARTY
Name: ____________________  Title: ____________________
Signature: ________________  Date: ____________________

RECEIVING PARTY
Name: ____________________  Title: ____________________
Signature: ________________  Date: ____________________
"""
    readme = f"""# {product} — Engineering dossier

Revision: A

This vendor-neutral dossier was generated by Hardware Foundry. Share it only after your NDA has been signed.

## Contents
- product_brief.json — submitted brief and constraints
- design_architecture.json — generated functional architecture
- engineering_design_report.md — design report, assumptions and risks
- candidate_bom.csv — candidate classes, not approved manufacturer part numbers
- functional_architecture.svg — visual system architecture
- mechanical_design_brief.md — mechanical requirements
- manufacturing_handoff.md — vendor-neutral hand-off instructions
- engineering_release_checklist.csv — outstanding engineering gates
- NDA_template.md — discussion template, not legal advice
- package_manifest.json — status and file completeness

## Release status
This is an engineering dossier, not a fabrication release. It does not contain Gerbers, NC drill, verified footprints, PCB CAD, pick-and-place coordinates or STEP enclosure CAD. Those must be produced from the product-specific circuit and mechanical design, checked and approved by a qualified engineer. No file here should be represented as factory-ready fabrication data.
"""
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", readme)
        archive.writestr("package_manifest.json", json.dumps(manifest, indent=2))
        archive.writestr("product_brief.json", json.dumps({"idea": brief, "constraints": payload.get("constraints", ""), "quantity": payload.get("quantity", 100)}, indent=2))
        archive.writestr("design_architecture.json", json.dumps(design, indent=2))
        archive.writestr("engineering_design_report.md", "".join(report))
        archive.writestr("candidate_bom.csv", bom.getvalue())
        archive.writestr("functional_architecture.svg", "".join(svg))
        archive.writestr("mechanical_design_brief.md", mechanical)
        archive.writestr("manufacturing_handoff.md", handoff)
        archive.writestr("engineering_release_checklist.csv", checklist.getvalue())
        archive.writestr("NDA_template.md", nda)
    return memory.getvalue(), f"{safe_name(product)}_Engineering_Dossier.zip"

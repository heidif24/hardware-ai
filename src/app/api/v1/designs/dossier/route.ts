import sharp from "sharp";
import {NextRequest, NextResponse} from "next/server";
import {strToU8, zipSync} from "fflate";

export const runtime = "nodejs";
export const maxDuration = 60;

type M = {id?: string; name: string; purpose: string; interfaces?: string[]; parts?: string[]};
type D = {
  decision_points?: {id: string; title: string; reason: string; options: {id: string; label: string; description: string; advantages: string[]; tradeoffs: string[]}[]}[];
  product_name: string;
  summary: string;
  assumptions?: string[];
  modules: M[];
  risks?: string[];
  engineering_specification?: Record<string, string | string[]>;
  validation_status?: string;
  estimated_complexity?: string;
};
type P = {
  idea: string;
  constraints?: string;
  quantity?: number;
  design: D;
  include_product_render?: boolean;
  decision_selections?: Record<string, string>;
  decision_notes?: Record<string, string>;
  global_notes?: string;
  design_approved?: boolean;
  engineering_plan?: Record<string, unknown>;
};

const clean = (v: unknown, d = "Not specified") => (typeof v === "string" && v.trim() ? v.trim() : d);
const list = (a: string[] | undefined) => (a?.length ? a.map((x) => "- " + x).join("\n") : "- To be defined during detailed engineering.");
const csv = (s: string) => '"' + s.replace(/"/g, '""') + '"';
const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 55) || "hardware-product";

function architectureSvg(d: D) {
  const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&", "<": "<", ">": ">", '"': """ }[c]!));
  const cards = d.modules.map((m, i) => {
    const y = 132 + i * 108;
    return `<rect x="55" y="${y}" width="890" height="80" rx="12" fill="#111b1a" stroke="#50604a"/><text x="82" y="${y + 29}" fill="#c1f27a" font-family="Arial" font-size="19" font-weight="bold">${esc(m.name)}</text><text x="82" y="${y + 55}" fill="#d3ded7" font-family="Arial" font-size="13">${esc(m.purpose.slice(0, 115))}</text>`;
  }).join("");
  const h = 170 + d.modules.length * 108;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="${h}" viewBox="0 0 1000 ${h}"><rect width="100%" height="100%" fill="#090f10"/><text x="55" y="42" fill="#c1f27a" font-family="Arial" font-size="12" letter-spacing="4">HARDWARE FOUNDRY / FUNCTIONAL ARCHITECTURE</text><text x="55" y="91" fill="#f1f5f2" font-family="Arial" font-size="25" font-weight="bold">${esc(d.product_name)}</text>${cards}<text x="55" y="${h - 20}" fill="#91a09b" font-family="Arial" font-size="11">CONCEPT ONLY — NOT A VERIFIED SCHEMATIC OR FABRICATION RELEASE</text></svg>`;
}

async function renderProductConcept(b: P, d: D): Promise<{png: Uint8Array; model: string} | null> {
  const token = process.env.REPLICATE_API_TOKEN;
  if (!token) return null;
  const model = process.env.REPLICATE_IMAGE_MODEL || "black-forest-labs/flux-1.1-pro";
  if (!/^[a-z0-9-]+\/[a-z0-9-]+$/i.test(model)) return null;
  const moduleSummary = d.modules.map((m) => m.name + ": " + m.purpose).join("; ").slice(0, 1400);
  const prompt = [
    "Photorealistic premium industrial-design 3D product concept of: " + b.idea.trim(),
    "Constraints: " + clean(b.constraints, "Not supplied"),
    "Architecture: " + moduleSummary,
    "Three-quarter front view, realistic materials, studio lighting, neutral background.",
    "No logos, text, people or watermark. Visual concept only, not dimensionally accurate CAD.",
  ].join("\n");
  try {
    const response = await fetch("https://api.replicate.com/v1/models/" + model + "/predictions", {
      method: "POST",
      headers: { Authorization: "Bearer " + token, "Content-Type": "application/json", Prefer: "wait=40", "Cancel-After": "50s" },
      body: JSON.stringify({ input: { prompt, aspect_ratio: "4:3", output_format: "png", output_quality: 100, safety_tolerance: 2, prompt_upsampling: true } }),
      signal: AbortSignal.timeout(45000),
    });
    if (!response.ok) return null;
    let prediction = (await response.json()) as { status?: string; output?: string | string[]; urls?: { get?: string } };
    let output = prediction.output;
    if (prediction.status !== "succeeded" || !output) {
      if (!prediction.urls?.get) return null;
      let current = prediction;
      for (let i = 0; i < 5 && current.status !== "succeeded"; i++) {
        await new Promise((r) => setTimeout(r, 1000));
        const poll = await fetch(current.urls?.get || prediction.urls.get, { headers: { Authorization: "Bearer " + token }, signal: AbortSignal.timeout(8000) });
        if (!poll.ok) return null;
        current = (await poll.json()) as typeof prediction;
      }
      output = current.output;
      if (current.status !== "succeeded" || !output) return null;
    }
    const imageUrl = Array.isArray(output) ? output[0] : output;
    if (typeof imageUrl !== "string") return null;
    const parsed = new URL(imageUrl);
    if (parsed.protocol !== "https:" || !(parsed.hostname === "replicate.delivery" || parsed.hostname.endsWith(".replicate.delivery"))) return null;
    const imageResponse = await fetch(parsed.toString(), { signal: AbortSignal.timeout(10000) });
    if (!imageResponse.ok) return null;
    const source = Buffer.from(await imageResponse.arrayBuffer());
    if (source.byteLength > 15 * 1024 * 1024) return null;
    const png = await sharp(source).png().toBuffer();
    return { png: new Uint8Array(png), model };
  } catch {
    return null;
  }
}

export async function POST(req: NextRequest) {
  try {
    const b = (await req.json()) as P;
    if (!b || typeof b.idea !== "string" || b.idea.trim().length < 8 || b.idea.length > 4000) {
      return NextResponse.json({ detail: "A product brief of 8–4,000 characters is required." }, { status: 422 });
    }
    const d = b.design;
    if (!d || typeof d.product_name !== "string" || !Array.isArray(d.modules) || !d.modules.length || d.modules.length > 20) {
      return NextResponse.json({ detail: "Generate a valid architecture before exporting." }, { status: 422 });
    }
    if (b.design_approved !== true) {
      return NextResponse.json({ detail: "Approve the design basis before exporting the engineering handover." }, { status: 409 });
    }
    const requiredDecisions = d.decision_points || [];
    const unresolved = requiredDecisions.filter((p) => !(p.options || []).some((o) => o.id === b.decision_selections?.[p.id]));
    if (unresolved.length) {
      return NextResponse.json({ detail: "Select an option for every engineering decision before exporting: " + unresolved.map((p) => p.title).join(", ") }, { status: 422 });
    }

    const now = new Date().toISOString();
    const productRender = b.include_product_render === true ? await renderProductConcept(b, d) : null;
    const assumptions = d.assumptions || [];
    const risks = d.risks || [];
    const architectureSvgStr = architectureSvg(d);
    const architecturePng = await sharp(Buffer.from(architectureSvgStr)).png().toBuffer();

    const plan = b.engineering_plan && typeof b.engineering_plan === "object" ? (b.engineering_plan as Record<string, unknown>) : null;
    const proposedSummary =
      plan && typeof plan.proposed_final_design_summary === "string" && String(plan.proposed_final_design_summary).trim().length > 20
        ? String(plan.proposed_final_design_summary).trim()
        : "Recommended prototype configuration for " +
          d.product_name +
          ": proceed from the approved design basis and functional architecture, freeze power and environmental requirements, then complete schematic, PCB, enclosure CAD and firmware under normal engineering review. This package is a structured briefing for detailed design, not a fabrication release.";

    const proposedFinal = [
      "# Proposed final design",
      "",
      "**Product:** " + d.product_name,
      "**Generated:** " + now,
      "**Status:** Proposed design basis for engineering hand-off",
      "",
      "## Summary for the engineering company",
      proposedSummary,
      "",
      "## Functional modules",
      ...d.modules.map((m, i) => i + 1 + ". **" + m.name + "** — " + m.purpose),
      "",
      "## Open work before fabrication",
      "- Select exact components from current datasheets",
      "- Capture and review schematic (ERC)",
      "- Complete PCB layout and DRC",
      "- Finalise enclosure CAD with controlled dimensions",
      "- Implement and test board-specific firmware",
      "- Run verification against the test plan",
      "",
      "This document presents the recommended starting point. It does not authorise fabrication.",
    ].join("\n");

    const decisionRows = (d.decision_points || [])
      .map((p) => {
        const selected = b.decision_selections?.[p.id] || "not_selected";
        const option = (p.options || []).find((o) => o.id === selected);
        return ["## " + p.title, "", "**Selected option:** " + (option?.label || selected), "", "**Engineering rationale:** " + p.reason, "", "**User clarification:** " + clean(b.decision_notes?.[p.id], "No additional note.")].join("\n");
      })
      .join("\n\n");

    const designReview = ["# Approved design basis", "", "**Approval state:** USER_APPROVED_FOR_DETAILED_ENGINEERING", "**Approved at:** " + now, "", "This records the user's provisional design choices. It is not engineering sign-off, certification or permission to fabricate.", "", decisionRows, "## Project-wide clarifications", "", clean(b.global_notes, "No additional project-wide clarification supplied.")].join("\n");

    const rows = d.modules.map((m) => "| " + m.name.replace(/\|/g, "/") + " | " + m.purpose.replace(/\|/g, "/") + " | " + (m.interfaces || []).join(", ") + " | " + (m.parts || []).join("; ") + " |").join("\n");
    const report = [
      "# Engineering design report", "",
      "**Product:** " + d.product_name,
      "**Generated:** " + now,
      "**Initial quantity:** " + (b.quantity || "Not specified"),
      "**Status:** " + clean(d.validation_status, "concept_only"), "",
      "## Summary", clean(d.summary), "",
      "## Proposed final design", "See 02_System_Architecture/proposed_final_design.md.", "",
      "## Functional architecture",
      "| Module | Purpose | Interfaces | Candidate classes |", "|---|---|---|---|", rows, "",
      "## Assumptions", list(assumptions), "",
      "## Risks and required work", list(risks), "",
      "## Design maturity",
      "This is a concept-level planning artefact, not a verified electrical design, mechanical CAD release, safety assessment, compliance report or approved manufacturing package.", "",
      "## Required gates",
      "1. Freeze requirements and measurable acceptance criteria.",
      "2. Select exact components using current datasheets.",
      "3. Capture schematics and complete ERC review.",
      "4. Create PCB layout and complete DRC.",
      "5. Develop enclosure CAD and verify fit.",
      "6. Build prototypes and record verification results.",
      "7. Complete regulatory assessment and qualified engineering sign-off.",
    ].join("\n");

    const requirements = ["# Requirements baseline", "", "## Product intent", b.idea.trim(), "", "## Constraints supplied", clean(b.constraints), "", "## Design assumptions", list(assumptions), "", "## Open risks", list(risks)].join("\n");

    const bom = ["Reference,Functional block,Candidate class,Selection status,Engineering note"];
    for (const m of d.modules) for (const p of m.parts || []) bom.push([m.id || m.name, m.name, p, "UNSELECTED — CANDIDATE ONLY", "Verify ratings, lifecycle, package, footprint and compliance against datasheet"].map(csv).join(","));

    const checklist = [
      "Asset,Required for fabrication hand-off,Package status",
      "Product requirements baseline,Yes,Included — concept level",
      "Functional architecture,Yes,Included — concept level",
      "Proposed final design,Yes,Included — concept level",
      "Candidate BOM,Yes,Functional classes only",
      "Manufacturer part numbers and datasheets,Yes,NOT INCLUDED",
      "KiCad schematic source,Yes,NOT INCLUDED",
      "PCB layout and Gerbers,Yes,NOT INCLUDED",
      "STEP enclosure CAD,As required,NOT INCLUDED",
      "Prototype verification evidence,Yes,NOT INCLUDED",
      "Qualified engineering approval,Yes,NOT PROVIDED",
    ].join("\n");

    const handoff = [
      "# Manufacturing hand-off notes", "",
      "This package is a controlled engineering discussion starter, not a fabrication release.", "",
      "1. Independently identify and vet the prospective engineering or manufacturing partner.",
      "2. Agree and sign a suitable mutual NDA before disclosing confidential technical information.",
      "3. Share only the minimum appropriate documents under the signed agreement.",
      "4. Complete missing electrical/mechanical CAD, verification and compliance under normal engineering process.",
      "5. Issue an approved fabrication package only after qualified engineering sign-off.", "",
      "**Release state: ENGINEERING_DOSSIER_NOT_FABRICATION_RELEASE**",
    ].join("\n");

    const nda = [
      "# Mutual confidentiality agreement — discussion template", "",
      "> TEMPLATE ONLY. Not legal advice. Not signed or effective until completed and executed by counsel-reviewed agreement.", "",
      "## Purpose",
      "Evaluation of a potential engineering or manufacturing relationship concerning: " + d.product_name + ".", "",
      "Obtain legal advice before disclosure.",
    ].join("\n");

    const included = [
      "package_manifest.json",
      "01_Product_Definition/product_brief.json",
      "01_Product_Definition/requirements_baseline.md",
      "01_Product_Definition/approved_design_basis.md",
      "02_System_Architecture/design_architecture.json",
      "02_System_Architecture/engineering_design_report.md",
      "02_System_Architecture/proposed_final_design.md",
      "02_System_Architecture/functional_architecture.svg",
      "02_System_Architecture/functional_architecture.png",
      "07_BOM_And_Assembly/candidate_bom.csv",
      "09_Testing_And_Validation/engineering_release_checklist.csv",
      "10_Manufacturing_Handover/manufacturing_handoff.md",
      "10_Manufacturing_Handover/NDA_template.md",
    ];
    if (productRender) included.push("08_Visualisation/product_concept_render.png");

    const manifest = {
      package_name: d.product_name,
      generated_at: now,
      release_state: "ENGINEERING_DOSSIER_NOT_FABRICATION_RELEASE",
      included_files: included,
      render_status: productRender ? "GENERATED" : "NOT_GENERATED",
    };

    const brief = {
      product_name: d.product_name,
      product_description: b.idea.trim(),
      engineering_constraints: clean(b.constraints),
      initial_production_quantity: b.quantity || null,
      generated_at: now,
    };

    const files: Record<string, Uint8Array> = {
      "package_manifest.json": strToU8(JSON.stringify(manifest, null, 2)),
      "01_Product_Definition/product_brief.json": strToU8(JSON.stringify(brief, null, 2)),
      "01_Product_Definition/requirements_baseline.md": strToU8(requirements),
      "01_Product_Definition/approved_design_basis.md": strToU8(designReview),
      "02_System_Architecture/design_architecture.json": strToU8(JSON.stringify(d, null, 2)),
      "02_System_Architecture/engineering_design_report.md": strToU8(report),
      "02_System_Architecture/proposed_final_design.md": strToU8(proposedFinal),
      "02_System_Architecture/functional_architecture.svg": strToU8(architectureSvgStr),
      "02_System_Architecture/functional_architecture.png": new Uint8Array(architecturePng),
      "07_BOM_And_Assembly/candidate_bom.csv": strToU8(bom.join("\n")),
      "09_Testing_And_Validation/engineering_release_checklist.csv": strToU8(checklist),
      "10_Manufacturing_Handover/manufacturing_handoff.md": strToU8(handoff),
      "10_Manufacturing_Handover/NDA_template.md": strToU8(nda),
    };
    if (productRender) {
      files["08_Visualisation/product_concept_render.png"] = productRender.png;
      files["08_Visualisation/README.md"] = strToU8("Product concept render included. Illustrative only — not dimensionally accurate CAD.");
    }

    const zip = zipSync(files, { level: 6 });
    return new NextResponse(zip as unknown as BodyInit, {
      status: 200,
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": 'attachment; filename="' + slug(d.product_name) + '-engineering-dossier.zip"',
        "Cache-Control": "no-store",
      },
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : "Could not create the engineering dossier.";
    console.error("Dossier export failed:", message);
    return NextResponse.json({ detail: message }, { status: 502 });
  }
}

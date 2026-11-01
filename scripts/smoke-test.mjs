import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import assert from "node:assert/strict";
import { unzipSync } from "fflate";

const port = 3210;
const base = "http://127.0.0.1:" + port;
const server = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "-p", String(port)], {
  stdio: "inherit",
  env: { ...process.env, PORT: String(port) },
});

async function waitForServer() {
  for (let i = 0; i < 40; i += 1) {
    if (server.exitCode !== null) throw new Error("Next.js server exited with " + server.exitCode);
    try {
      const response = await fetch(base);
      if (response.ok) return;
    } catch {}
    await delay(750);
  }
  throw new Error("Next.js server did not become ready");
}

try {
  await waitForServer();
  const brief = {
    idea: "A compact solar-powered environmental sensor with wireless reporting",
    constraints: "Outdoor use, low power, weather-resistant enclosure; unknown battery runtime.",
    quantity: 100,
  };
  const synthesis = await fetch(base + "/api/v1/designs/synthesize", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(brief),
  });
  assert.equal(synthesis.status, 200, "synthesis endpoint must return HTTP 200");
  const design = await synthesis.json();
  assert.ok(Array.isArray(design.modules) && design.modules.length > 0, "synthesis must return functional modules");
  assert.ok(Array.isArray(design.decision_points) && design.decision_points.length >= 4, "synthesis must return engineering decision points");

  const blockedExport = await fetch(base + "/api/v1/designs/dossier", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ...brief, design, include_product_render: false }),
  });
  assert.equal(blockedExport.status, 409, "dossier export must require design-basis approval");

  const decision_selections = Object.fromEntries(design.decision_points.map((decision) => [decision.id, decision.recommended]));
  const dossier = await fetch(base + "/api/v1/designs/dossier", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      ...brief,
      design,
      include_product_render: false,
      decision_selections,
      design_approved: true,
      global_notes: "Smoke test clarification",
    }),
  });
  assert.equal(dossier.status, 200, "approved dossier endpoint must return HTTP 200");
  assert.ok((dossier.headers.get("content-type") || "").includes("application/zip"), "dossier must be a ZIP");

  const archive = unzipSync(new Uint8Array(await dossier.arrayBuffer()));
  const required = [
    "01_Product_Definition/README.md",
    "package_manifest.json",
    "01_Product_Definition/approved_design_basis.md",
    "02_System_Architecture/design_architecture.json",
    "07_BOM_And_Assembly/candidate_bom.csv",
    "02_System_Architecture/functional_architecture.svg",
    "02_System_Architecture/functional_architecture.png",
    "02_System_Architecture/engineering_design_report.md",
    "09_Testing_And_Validation/engineering_release_checklist.csv",
  ];
  for (const name of required) assert.ok(archive[name], "ZIP must contain " + name);

  const png = archive["02_System_Architecture/functional_architecture.png"];
  assert.deepEqual(Array.from(png.slice(0, 8)), [137, 80, 78, 71, 13, 10, 26, 10], "architecture preview must be a valid PNG");
  const width = new DataView(png.buffer, png.byteOffset, png.byteLength).getUint32(16);
  const height = new DataView(png.buffer, png.byteOffset, png.byteLength).getUint32(20);
  assert.ok(width >= 800 && height >= 300, "architecture PNG must have useful dimensions");

  const manifest = JSON.parse(new TextDecoder().decode(archive["package_manifest.json"]));
  assert.ok(manifest.included_files.includes("02_System_Architecture/functional_architecture.png"), "manifest must list the architecture PNG");
  assert.ok(manifest.included_files.includes("01_Product_Definition/approved_design_basis.md"), "manifest must list the approved design basis");
  assert.ok(manifest.missing_visual_assets.some((asset) => asset.includes("Photorealistic product concept PNG")), "manifest must disclose an unconfigured product render");
  console.log("Smoke test passed: synthesis -> decision approval -> structured dossier ZIP -> " + width + "x" + height + " PNG; " + Object.keys(archive).length + " files.");
} finally {
  server.kill("SIGTERM");
}

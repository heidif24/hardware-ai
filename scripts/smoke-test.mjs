import { spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import assert from "node:assert/strict";
import { unzipSync } from "fflate";

const port = 3210;
const base = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "-p", String(port)], {
  stdio: "inherit",
  env: { ...process.env, PORT: String(port) },
});

async function waitForServer() {
  for (let i = 0; i < 40; i += 1) {
    if (server.exitCode !== null) throw new Error(`Next.js server exited with ${server.exitCode}`);
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
  const integrationStatus = await fetch(`${base}/api/v1/integrations/status`);
  assert.equal(integrationStatus.status, 200, "integration status endpoint must return HTTP 200");
  const status = await integrationStatus.json();
  assert.ok(Array.isArray(status.integrations) && status.integrations.some((item) => item.id === "supplier-mouser"), "integration status must list supplier adapters");
  assert.equal(status.security.secrets_returned, false, "integration status must never return secrets");

  const invalidSupplierSearch = await fetch(`${base}/api/v1/sourcing/search`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query: "x" }),
  });
  assert.equal(invalidSupplierSearch.status, 422, "supplier search must validate query length");

  const brief = {
    idea: "A compact solar-powered environmental sensor with wireless reporting",
    constraints: "Outdoor use, low power, weather-resistant enclosure; unknown battery runtime.",
    quantity: 100,
  };

  const synthesis = await fetch(`${base}/api/v1/designs/synthesize`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(brief),
  });
  assert.equal(synthesis.status, 200, "synthesis endpoint must return HTTP 200");
  const design = await synthesis.json();
  assert.ok(Array.isArray(design.modules) && design.modules.length > 0, "synthesis must return functional modules");

  const dossier = await fetch(`${base}/api/v1/designs/dossier`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ ...brief, design, include_product_render: false }),
  });
  assert.equal(dossier.status, 200, "dossier endpoint must return HTTP 200");
  assert.match(dossier.headers.get("content-type") || "", /application\/zip/, "dossier must be a ZIP");

  const archive = unzipSync(new Uint8Array(await dossier.arrayBuffer()));
  const required = [
    "README.md",
    "package_manifest.json",
    "design_architecture.json",
    "candidate_bom.csv",
    "functional_architecture.svg",
    "functional_architecture.png",
    "engineering_design_report.md",
    "engineering_release_checklist.csv",
  ];
  for (const name of required) assert.ok(archive[name], `ZIP must contain ${name}`);

  const png = archive["functional_architecture.png"];
  assert.deepEqual(Array.from(png.slice(0, 8)), [137, 80, 78, 71, 13, 10, 26, 10], "architecture preview must be a valid PNG");
  const width = new DataView(png.buffer, png.byteOffset, png.byteLength).getUint32(16);
  const height = new DataView(png.buffer, png.byteOffset, png.byteLength).getUint32(20);
  assert.ok(width >= 800 && height >= 300, "architecture PNG must have useful dimensions");

  const manifest = JSON.parse(new TextDecoder().decode(archive["package_manifest.json"]));
  assert.ok(manifest.included_files.includes("functional_architecture.png"), "manifest must list the architecture PNG");
  assert.ok(manifest.missing_visual_assets.some((asset) => asset.includes("Photorealistic product concept PNG")), "manifest must explicitly disclose an unconfigured product render");
  console.log(`Smoke test passed: synthesis -> dossier ZIP -> ${width}x${height} PNG; ${Object.keys(archive).length} files.`);
} finally {
  server.kill("SIGTERM");
}

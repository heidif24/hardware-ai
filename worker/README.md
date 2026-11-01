# Hardware Foundry engineering worker

This is the separate container service for long-running engineering-tool execution. It is intentionally separate from the Vercel web application: KiCad, FreeCAD and embedded compiler toolchains are not suitable for short-lived serverless functions.

## What it does now

- Authenticates server-to-server requests with a bearer token.
- Stores approved design-basis snapshots and job state on a persistent volume.
- Probes the installed KiCad, FreeCAD, ARM and AVR toolchains.
- Accepts native engineering source files as base64-encoded job inputs (50 MB total limit).
- Runs KiCad ERC/DRC and exports Gerber/drill files only when the corresponding real project files are present and the DRC command passes.
- Detects firmware source but does not execute untrusted Makefiles; board-specific compilation remains gated on a frozen MCU, trusted build definition and SDK.
- Performs a basic STEP-file header check.
- Produces a ZIP containing actual supplied/generated files, execution results and an explicit report of missing work.

The worker limits submissions to two concurrent jobs and twenty new jobs per 24 hours. The public Vercel bridge does not forward arbitrary uploaded source files. The worker does **not** invent component selections, pin assignments, PCB geometry, enclosure dimensions, firmware or validation evidence. A job with incomplete source files is returned as `BLOCKED`, not falsely marked complete. A passed tool invocation is not engineering sign-off or certification.

## Deploy on Fly.io

Run these commands from the repository's `worker/` directory after installing and authenticating the Fly CLI:

```bash
fly apps create hardware-foundry-engineering-worker
fly volumes create hardware_foundry_jobs --region ams --size 20
```

Generate a long random secret locally and set it without sending it through ChatGPT:

```bash
fly secrets set WORKER_API_TOKEN="<generated-secret>"
fly deploy
```

Use the same secret in Vercel as `ENGINEERING_WORKER_TOKEN`, and set `ENGINEERING_WORKER_URL` to the HTTPS Fly app URL. Do not commit either secret.

The Fly app requires a persistent volume mounted at `/data`. The included `fly.toml` requests a 4 GB, 2-vCPU performance machine in Amsterdam. Adjust capacity after measuring real project sizes and tool execution times.

## API

- `GET /health` — unauthenticated liveness check.
- `GET /v1/toolchains` — authenticated toolchain inventory.
- `POST /v1/jobs` — submit an approved design basis and optional native source files.
- `GET /v1/jobs/{job_id}` — retrieve status and validation results.
- `GET /v1/jobs/{job_id}/artifact` — download the execution ZIP when the job reaches `BLOCKED` or `SUCCEEDED`.

The Vercel application proxies these through `/api/v1/engineering/jobs`.

## Operational boundary

This initial worker is an execution and validation foundation. It is not yet the AI engineering agent that creates a complete, electrically correct KiCad design, a dimensionally controlled FreeCAD model or board-specific firmware. Those generators must be added as separate, testable stages with manufacturer-datasheet grounding, requirement traceability and review gates. Never release Gerbers, STEP or binaries as fabrication-ready without qualified engineering review and prototype verification.

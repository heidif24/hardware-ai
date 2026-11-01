# Hardware Foundry engineering worker

This is the separate container service for long-running engineering-tool execution. It is intentionally separate from the Vercel web application: KiCad, FreeCAD and embedded compiler toolchains are not suitable for short-lived serverless functions.

## Self-contained open-source engineering stack

The worker image installs and owns the native engineering executables. The web application does not need separate CAD APIs:

- **KiCad** — schematic/PCB inspection, ERC/DRC and manufacturing exports.
- **FreeCAD** — parametric mechanical CAD execution and STEP-based workflows.
- **PlatformIO** — embedded firmware build environment when a target and trusted project definition are generated.
- **ARM/AVR GCC + CMake/Ninja** — lower-level embedded and portable firmware builds.

For local development, set a private `WORKER_API_TOKEN` and run:

```bash
WORKER_API_TOKEN="your-private-token" docker compose -f docker-compose.engineering.yml up --build
```

The frontend still communicates with the worker through one internal HTTP boundary. That boundary is an architectural separation for long-running jobs, not a dependency on a commercial CAD API.

## What it does now

- Authenticates server-to-server requests with a bearer token.
- Stores approved design-basis snapshots and job state on a persistent volume.
- Probes the installed KiCad, FreeCAD, ARM and AVR toolchains.
- Accepts native engineering source files as base64-encoded job inputs (50 MB total limit).
- Runs KiCad ERC/DRC and exports Gerber/drill files only when the corresponding real project files are present and the DRC command passes.
- Detects firmware source but does not execute untrusted Makefiles; board-specific compilation remains gated on a frozen MCU, trusted build definition and SDK.
- Performs a basic STEP-file header check.
- Receives a structured AI engineering plan and stores it with the approved design snapshot.\n- Refuses to treat model-generated READY labels as engineering evidence; the plan API forces native stages to BLOCKED until independently verified source inputs and review evidence are supplied.\n- Produces a ZIP containing actual supplied/generated files, execution results and an explicit report of missing work.

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

## AI intelligence integration point

The engineering worker is ready to receive a structured, approved design from the AI layer through `POST /v1/jobs`. The AI plan endpoint (`POST /api/v1/engineering/plan`) converts the approved concept into a structured plan covering electronics, PCB, firmware, mechanical design, interfaces, manufacturing and verification. The plan is stored by the worker. At present, the platform deliberately blocks native generation because the app does not yet ingest a verified component/datasheet/footprint source package or frozen board-specific requirements. The worker then records every missing input instead of guessing. Keep AI credentials outside the browser and inject them only into the server-side intelligence service.

Recommended flow:

```text
Natural-language brief -> AI requirement extraction -> design review -> user approval
-> engineering job -> KiCad / FreeCAD / PlatformIO worker -> validation -> ZIP
```

## Operational boundary

This initial worker is an execution and validation foundation. It is not yet the AI engineering agent that creates a complete, electrically correct KiCad design, a dimensionally controlled FreeCAD model or board-specific firmware. Those generators must be added as separate, testable stages with manufacturer-datasheet grounding, requirement traceability and review gates. Never release Gerbers, STEP or binaries as fabrication-ready without qualified engineering review and prototype verification.


## Where the production worker URL comes from

The URL is assigned by Fly.io after the worker app is created and deployed. With the app name in `fly.toml`, the expected default URL is:

`https://hardware-foundry-engineering-worker.fly.dev`

If Fly reports that the app name is already taken, choose an available globally unique name, update `app = "..."` in `fly.toml`, and use `https://YOUR-APP-NAME.fly.dev` instead.

From the repository's `worker/` directory:

```bash
fly auth login
fly apps create hardware-foundry-engineering-worker
fly volumes create hardware_foundry_jobs --region ams --size 20
openssl rand -hex 32
# Copy the generated value locally; do not commit it.
fly secrets set WORKER_API_TOKEN="PASTE_THE_GENERATED_VALUE"
fly deploy
```

Then add these production environment variables in the Vercel project settings:

- `ENGINEERING_WORKER_URL=https://hardware-foundry-engineering-worker.fly.dev`
- `ENGINEERING_WORKER_TOKEN` = exactly the same secret value set as `WORKER_API_TOKEN` on Fly.io.

Redeploy the Vercel application after adding the variables. Check worker liveness by opening `https://YOUR-APP-NAME.fly.dev/health`; it should return JSON with `status: ok`. Keep the worker token private.

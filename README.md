# Hardware Foundry

Vercel-hosted product engineering workspace. Turn a product idea into a complete, cost-aware engineering package that an engineering company can use to produce a first prototype.

## End-to-end goal

1. Describe the device and constraints.
2. Generate a functional architecture and provisional engineering decisions.
3. Review alternatives (including cost and durability trade-offs) and approve a design basis.
4. Generate an AI engineering plan with generation gates.
5. Download a structured engineering dossier ZIP (and, when the worker is connected, a native execution package).
6. Share the package with an engineering company under NDA so they can complete detailed design and build a prototype.

The package is intentionally **not** a fabrication release. It is a strong, honest briefing designed so a competent engineering firm can move quickly and cost-effectively.

## What the complete package contains

- Product brief, approved design basis and user clarifications
- Functional architecture (JSON + SVG + PNG diagram)
- Photorealistic product concept PNG (when Replicate is configured)
- Engineering design report and device specification
- Cost & durability alternatives (conventional / optimised / novel)
- Candidate functional BOM
- Interface control document, firmware and mechanical plans
- Verification plan, release checklist, manufacturing hand-off notes and NDA discussion template
- When the engineering worker runs: AI plan, innovation dossier, toolchain probe results, and any native artefacts that passed evidence gates (parametric FreeCAD enclosure, PlatformIO firmware build, proprietary connector geometry, KiCad ERC/DRC/Gerbers on real source files)

## AI generation: multiple providers

The synthesis and engineering-plan APIs support three independent providers and server-side failover:

1. Google Gemini
2. Groq
3. OpenAI

Default order: Gemini → Groq → OpenAI. Configure `AI_PROVIDER_ORDER` to change it. If no provider succeeds, a deterministic baseline architecture is returned for synthesis.

### Vercel environment variables

Server-side only (never `NEXT_PUBLIC_`):

- `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`
- Optional model overrides: `GEMINI_MODEL`, `GROQ_MODEL`, `OPENAI_MODEL`
- `AI_PROVIDER_ORDER` (default `gemini,groq,openai`)
- `REPLICATE_API_TOKEN` (+ optional `REPLICATE_IMAGE_MODEL`) for photorealistic concept renders
- `ENGINEERING_WORKER_URL` + `ENGINEERING_WORKER_TOKEN` for the native worker

## Photorealistic product concept rendering

When `REPLICATE_API_TOKEN` is set, the dossier can include a product-specific 3D concept image via `black-forest-labs/flux-1.1-pro` (or another official Replicate model). The image is a visual concept only — not dimensionally accurate CAD or manufacturing evidence.

## Generative engineering and cost-aware alternatives

Every approved design can produce three comparison paths:

- **Conventional** — lowest validation uncertainty, standard modules
- **Optimised** — preferred default for a first cost-effective, durable prototype
- **Foundry innovation** — novel interface/geometry only when evidence can justify it

The worker records the comparison criteria and the evidence still required before any novel idea can be released.

## Native engineering worker

A separate container (`worker/`) is intended for Fly.io (or local Docker Compose). It contains KiCad, FreeCAD, PlatformIO and GCC toolchains.

Native generators are **evidence-gated**:

- Firmware compiles only with a verified PlatformIO board + reviewed application source
- FreeCAD enclosure/STEP only with provenance-labelled dimensions
- Proprietary connector geometry only with provenance-labelled geometry parameters
- KiCad ERC/DRC/Gerber only on real supplied project files

Missing evidence produces a clear `BLOCKED` status rather than invented files.

See `worker/README.md` and `docker-compose.engineering.yml`.

## Local development

```bash
npm install
cp .env.example .env.local   # add provider keys
npm run dev
```

Optional engineering worker:

```bash
WORKER_API_TOKEN="generate-a-long-random-secret" docker compose -f docker-compose.engineering.yml up --build
```

## Engineering integrity

Hardware Foundry distinguishes concept artefacts from verified schematics, CAD, PCB outputs and production files. Approval of a design basis is not engineering sign-off or permission to fabricate. Obtain legal review of any NDA before confidential disclosure.

**Release state of the dossier:** `ENGINEERING_DOSSIER_NOT_FABRICATION_RELEASE`

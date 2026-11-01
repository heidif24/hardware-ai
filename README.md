# Hardware Foundry

Vercel-hosted product engineering workspace. Generate a first-pass functional architecture and download a vendor-neutral engineering dossier. Users control manufacturer contact and disclosure.

## AI generation: multiple providers

The synthesis API supports three independent providers and server-side failover:

1. Google Gemini
2. Groq
3. OpenAI

By default the app tries Gemini, then Groq, then OpenAI. It skips providers without configured keys and continues to the next provider if a request fails, times out or returns an invalid architecture. Configure `AI_PROVIDER_ORDER` to change the order, for example `groq,gemini,openai`. If no configured provider succeeds, a deterministic baseline architecture is returned.

### Vercel environment variables

Add these in Project → Settings → Environment Variables. Keep them server-side; do not use `NEXT_PUBLIC_` prefixes.

- `GEMINI_API_KEY` — Google AI Studio API key.
- `GROQ_API_KEY` — Groq API key.
- `OPENAI_API_KEY` — optional OpenAI API key.
- `GEMINI_MODEL` — optional; default `gemini-2.5-flash`.
- `GROQ_MODEL` — optional; default `llama-3.3-70b-versatile`.
- `OPENAI_MODEL` — optional; default `gpt-4.1-mini`.
- `AI_PROVIDER_ORDER` — optional; default `gemini,groq,openai`.

At least one provider key is needed for AI-assisted generation. It is recommended to configure both Gemini and Groq, and optionally OpenAI as a third fallback. Redeploy after changing environment variables.

## Photorealistic product concept rendering

The full dossier export can generate a product-specific photorealistic 3D concept image using Replicate's official `black-forest-labs/flux-1.1-pro` model. Configure `REPLICATE_API_TOKEN` in Vercel Project → Settings → Environment Variables. Optionally set `REPLICATE_IMAGE_MODEL` to another Replicate official model in `owner/model` format. The default model is metered per generated image; check the provider's current pricing before enabling it. The export includes `product_concept_render.png` only when a real render has completed. It does not substitute the architecture diagram or a placeholder. Without the token, the engineering ZIP still downloads and explicitly records that the product render was not generated.

The render is a visual concept, not dimensionally accurate CAD, a validated enclosure, a verified circuit, or manufacturing evidence. The separate `functional_architecture.png` is a raster diagram preview.

## Generative engineering and Foundry interface family

Hardware Foundry now treats novelty as an engineering candidate rather than a cosmetic choice. Every approved design can produce three comparison paths: a conventional baseline, a proven optimisation path, and a Foundry innovation path. The worker records the comparison criteria and the evidence required before a novel idea can be released.

The reusable **Foundry Interface Family** is generated from shared design DNA rather than a hardcoded connector catalogue. The system selects or proposes a family variant according to electrical roles, power envelope, signalling, environment, mating cycles, cable strain and enclosure constraints. Generated family definitions are **concept-level contracts** until component selection, pin assignments, tolerance analysis and prototype testing are complete.

## Product workflow

1. Enter a product brief and known engineering constraints.
2. Generate a functional architecture and provisional engineering decisions.
3. Review recommendations, alternatives, trade-offs and add notes or clarifications.
4. Approve the design basis; editing the brief or decisions invalidates that approval.
5. Download the structured engineering dossier ZIP.
6. When the separate worker is connected, submit a toolchain execution job and download its execution report.
7. Independently approach manufacturers and obtain a signed NDA before sharing confidential information.

## Project persistence and operational limits

The current app automatically saves the latest brief and generated architecture in the browser's local storage on that device and browser. It does not yet provide user accounts, cloud project storage, cross-device synchronisation, team workspaces or a project database. 

## Application and engineering-worker architecture

The Next.js application and AI synthesis APIs run on Vercel. A separate container worker in `worker/` is designed for Fly.io because KiCad, FreeCAD and embedded toolchains are not suitable for Vercel serverless functions. The Vercel API proxies approved job requests to the worker using `ENGINEERING_WORKER_URL` and `ENGINEERING_WORKER_TOKEN`; the worker uses `WORKER_API_TOKEN` and a persistent volume for job state. See `worker/README.md` for deployment instructions. The worker currently probes toolchains and validates actual native files when securely supplied; it reports missing artefacts rather than fabricating them.

## Local development

Run `npm install`, copy `.env.example` to `.env.local`, add provider keys as required, then run `npm run dev`.

## Engineering integrity and release limits

The generated ZIP includes product brief, architecture JSON, functional architecture SVG and a rendered `functional_architecture.png` preview, and (when Replicate is configured) a photorealistic `product_concept_render.png`, engineering report, requirements baseline, candidate functional BOM, interface control document, firmware and mechanical plans, verification plan, manufacturing hand-off notes, release checklist and an NDA discussion template.

The application currently generates concept-level planning artefacts and a provisional user-approved design basis. The separate worker foundation can probe its installed toolchains and execute checks on actual supplied KiCad/STEP files, but the public Vercel bridge does not yet provide native-file upload. The system does not yet generate actual KiCad schematics, verified symbols or footprints, PCB layout source, Gerber X2, NC drill, IPC-356 netlist, pick-and-place data, assembly drawings, dimensionally accurate STEP enclosure CAD, board-specific compiled firmware, prototype verification evidence or qualified engineering approval. Those require the next product-specific AI engineering and CAD/EDA generation stages, grounded component data, validation and qualified review.

The NDA file is a discussion template, not legal advice or proof of an executed agreement. Obtain appropriate legal review and signatures before confidential disclosure.


## Self-contained engineering environment

The repository includes `docker-compose.engineering.yml` and a dedicated worker image containing KiCad, FreeCAD, PlatformIO, ARM/AVR GCC, CMake and Ninja. These are native open-source execution engines, so the platform does not require separate commercial CAD APIs.

Run the engineering environment locally with:

```bash
WORKER_API_TOKEN="generate-a-long-random-secret" docker compose -f docker-compose.engineering.yml up --build
```

Set `ENGINEERING_WORKER_URL` and `ENGINEERING_WORKER_TOKEN` only on the server-side application environment. AI intelligence credentials should likewise remain server-side. The user interacts only with Hardware Foundry.


## Native engineering execution engines

The worker now contains evidence-gated native generation adapters in `worker/app/engines.py`:

- **Firmware:** creates a PlatformIO project and invokes a real `platformio run` build only when the approved engineering plan includes a verified PlatformIO board identifier, supported framework, and reviewed board-specific application source. Compiler output and build status are included in the execution record.
- **Mechanical CAD:** creates a FreeCAD macro for a parametric enclosure and invokes `FreeCADCmd` to produce editable `.FCStd` and neutral `.step` files only when length, width, height, wall, floor and corner parameters have explicit user/source/calculation provenance and pass geometric consistency checks.
- **Electronics/PCB:** validates actual supplied KiCad schematics and boards with KiCad CLI; successful board DRC triggers Gerber and drill export. The worker does not invent verified component pinouts, footprints, board stackups or routes from incomplete concept data.
- **Cross-stage release:** generated files are inventoried in the execution package. A stage that lacks required engineering evidence remains BLOCKED; a successful CAD/firmware tool invocation is not prototype or regulatory certification.

### Engineering worker environment

Required Vercel server-side variables:
- `ENGINEERING_WORKER_URL`: HTTPS base URL of the deployed worker (for Fly, the app hostname shown by `fly apps list`).
- `ENGINEERING_WORKER_TOKEN`: bearer token shared with the worker as `WORKER_API_TOKEN`.

Required worker secret:
- `WORKER_API_TOKEN`: long random secret; configure with Fly secrets, never commit it.

AI generation requires at least one provider key: `GEMINI_API_KEY`, `GROQ_API_KEY`, or `OPENAI_API_KEY`. These credentials are independent of worker deployment. The worker health endpoint is public and reports service availability only; authenticated toolchain and job endpoints require the bearer token.

The engineering worker uses a persistent Fly volume for job state. Queued jobs are resumed after process startup; a job interrupted during a native tool invocation is marked failed with partial workspace artefacts retained for diagnosis. Do not treat a queued job as completed until the status endpoint reports a terminal result and the archive is downloadable.

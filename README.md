# Hardware Foundry

AI-assisted hardware product engineering workspace. The platform takes a product brief through functional architecture and a structured engineering dossier, then stops at a confidential, vendor-neutral download. The user independently approaches manufacturers and controls disclosure.

## Product workflow

1. Submit a detailed product brief and engineering constraints.
2. Generate a first-pass functional architecture and product requirements baseline.
3. Generate electrical design planning, interface control, firmware planning, mechanical design requirements and a verification plan.
4. Generate a product concept render when an image-generation API key is configured.
5. Save projects to the private account vault.
6. Export a vendor-neutral ZIP engineering dossier, including an NDA discussion template and an engineering release checklist.
7. Share the dossier with a manufacturer only after an NDA has been agreed and signed.

## What the platform deliberately does not do

- No supplier discovery, supplier pricing, procurement or component ordering.
- No factory quotation or order submission.
- No automatic disclosure to manufacturers.
- No claim that a concept is a validated circuit or a fabrication-ready product.

## Engineering integrity

A generated dossier contains the product brief, architecture JSON, requirements baseline, engineering design report, candidate functional BOM, interface control document, firmware plan, mechanical design brief, verification plan, architecture SVG, manufacturing hand-off notes, NDA template and engineering release checklist.

The current synthesis stage is concept-level. It does **not** generate actual KiCad schematics, verified component footprints, PCB layout, Gerber X2, NC drill, IPC-356 netlist, centroid / pick-and-place, assembly drawings or dimensionally accurate STEP enclosure files. Those require product-specific circuit and mechanical engineering, EDA capture, ERC/DRC, and qualified engineer review. The export manifest identifies those missing fabrication assets explicitly. Never represent the concept dossier as an approved manufacturing release.

## Architecture

- Frontend: Next.js 15 App Router, TypeScript and TailwindCSS on Vercel.
- Backend: FastAPI on Render.
- Persistence: PostgreSQL with SQLAlchemy; SQLite fallback for local development.
- Authentication: Argon2 password hashing and JWT sessions.
- AI: OpenAI structured engineering planning and GPT Image generation; Replicate image fallback.
- Exports: vendor-neutral ZIP dossier generated server-side.

## Deployment

### Backend on Render

1. Open Render and create a new Blueprint from this repository.
2. Render reads `render.yaml`, provisions the FastAPI service and PostgreSQL database.
3. Set `OPENAI_API_KEY` on the backend when ready. This enables AI-assisted engineering synthesis and OpenAI product concept renders.
4. Optionally set `REPLICATE_API_TOKEN` as an image-generation fallback.
5. Confirm `FRONTEND_ORIGINS` contains the exact Vercel production domain.
6. Verify the backend health endpoint at `https://YOUR-RENDER-SERVICE/health`.

### Frontend on Vercel

1. Add `BACKEND_API_URL` as a server-side Production environment variable, set to the Render service base URL (for example `https://hardware-foundry-api.onrender.com`, with no trailing path).
2. Redeploy the Vercel project.
3. Test synthesis, project registration/login, project saving, visual generation (after adding an image key), and engineering dossier ZIP export.

Never expose provider credentials through `NEXT_PUBLIC_*` variables. Never paste API keys into source control or chat.

## Local development

Frontend:
```bash
npm install
npm run dev
```

Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Set `BACKEND_API_URL=http://localhost:8000` for the Next.js server. For local SQLite, no database variable is required.

## Release gate

A successful web deployment is not the same as a completed hardware engineering release. A specific product is ready for manufacturer fabrication only after its electrical and mechanical CAD files exist, ERC/DRC and relevant validation have been completed, and a qualified engineer has approved the revision-controlled package.

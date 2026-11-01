# Hardware Foundry

AI-assisted hardware product development workspace: invention brief → functional architecture → component sourcing → visual concept → project vault → factory RFQ preparation.

## Architecture
- **Frontend:** Next.js 15 App Router, TypeScript, TailwindCSS, hosted on Vercel.
- **Backend:** FastAPI/Python, hosted independently (Render blueprint included).
- **Persistence:** PostgreSQL with SQLAlchemy; local SQLite fallback for development.
- **Accounts:** Argon2 password hashing and JWT bearer sessions.
- **Synthesis:** OpenAI structured JSON generation when configured; deterministic fallback without an API key.
- **Supplier intelligence:** Mouser Search API and DigiKey OAuth2/product search adapters. LCSC is currently a catalogue link-out; live LCSC stock is not claimed without an authorised feed.
- **Visuals:** OpenAI image generation (gpt-image-1) or Replicate Flux fallback; downloadable PNG concept render.
- **Manufacturing:** Candidate BOM, architecture SVG, engineering specification and RFQ-preparation ZIP. The pack explicitly identifies missing fabrication outputs.

## Deploy
1. Deploy the FastAPI service using render.yaml; provision its PostgreSQL database and set the generated SECRET_KEY.
2. Set OPENAI_API_KEY, MOUSER_API_KEY, DIGIKEY_CLIENT_ID, DIGIKEY_CLIENT_SECRET, and/or REPLICATE_API_TOKEN in the backend environment as available. OpenAI key enables synthesis and product visual generation.
3. Set FRONTEND_ORIGINS to the exact Vercel production domain.
4. In Vercel, set BACKEND_API_URL to the Render service base URL (no trailing path), then redeploy.
5. Never expose provider credentials through NEXT_PUBLIC_* variables.

## Local development
Frontend: npm install && npm run dev.
Backend: cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000.
Set BACKEND_API_URL=http://localhost:8000 in the Next.js server environment.

## Supplier coverage and engineering truth
Supplier search only marks returned distributor records as live-verified. Provider credentials, API permissions, regional catalogues and rate limits apply. LCSC currently opens its catalogue search page; do not treat a search link as verified stock or pricing.

The generated product image is a concept render, not a dimensionally accurate CAD model. The RFQ package is a preparation dossier, not a fabrication release. It does not claim to contain verified schematics, PCB layout, Gerbers, drill files, IPC netlists, footprints or centroid data. Those must be produced from an electrically complete design in EDA software, checked with ERC/DRC, and reviewed by a qualified hardware engineer before any factory order. JLCPCB and PCBWay quote/order submission remains a human-reviewed vendor hand-off; no unsupported private factory API is represented as integrated.

## Current release scope
Functional architecture, supplier adapters, visual generation endpoint, account registration/login, project persistence, candidate BOM export, architecture SVG and RFQ preparation are implemented. Production readiness still depends on configuring provider credentials, deploying the backend/database, and completing the physical electronics engineering and validation process for each design.

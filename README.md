# Hardware Foundry

AI-native hardware product development workspace. From a natural-language invention brief to a modular architecture, candidate components and a manufacturing preparation pathway.

## Foundation
- Next.js 15 App Router, TypeScript and TailwindCSS studio.
- FastAPI + Pydantic backend.
- Functional mesh decomposes concepts into Power, Processing, Sensing, Connectivity, Interface and Actuation.
- OpenAI-assisted JSON architecture when configured; deterministic fallback otherwise.
- Concept JSON and candidate-BOM ZIP export.

## Run
Frontend: npm install && npm run dev. Backend: cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000. Configure NEXT_PUBLIC_API_URL and backend OPENAI_API_KEY independently.

## Roadmap
Persistent projects and auth; credential-backed Mouser, DigiKey and LCSC catalogues; schematic generation and electrical simulation; deterministic PCB generation through KiCad CLI with DRC and engineer sign-off; STEP enclosure and product visualisation; factory rules, quantity costing and quote adapters.

## Release integrity
Concept packages are not fabrication releases. Gerber, drill and centroid files must be generated from a verified PCB layout, checked against current factory rules and reviewed by a qualified engineer. Factory submission requires a supported integration and explicit user approval. Never expose API secrets through NEXT_PUBLIC variables.

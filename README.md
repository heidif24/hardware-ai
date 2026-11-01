# Hardware Foundry

Hardware Foundry is a Vercel-hosted product engineering workspace. It turns a product brief into a first-pass functional architecture and a downloadable, vendor-neutral engineering dossier. The user controls manufacturer contact and disclosure.

## Product workflow

1. Enter a product brief and known engineering constraints.
2. Generate a first-pass functional architecture.
3. Review functional modules, interfaces, assumptions and risks.
4. Download the design JSON or a complete engineering dossier ZIP.
5. Independently approach manufacturers. Negotiate and obtain a signed NDA before sharing confidential design information.

## Deliberately out of scope

- Supplier discovery, supplier pricing, quotes or procurement.
- Component ordering or factory order submission.
- Automatic manufacturer contact, file sharing or NDA signature verification.
- Claims that a concept is a validated circuit or fabrication-ready product.

## Vercel-only architecture

- Frontend: Next.js App Router, TypeScript and Tailwind CSS.
- Server routes: Next.js Route Handlers running as Vercel Node.js Functions.
- AI: Optional OpenAI API call from the server-side synthesis route. A deterministic baseline architecture is returned when no API key is configured or the provider is unavailable.
- Dossier export: ZIP archive generated in the Vercel function using fflate.
- Persistence: No external database is required by the current single-session workflow. Account registration, login and cloud project storage are intentionally not exposed until a durable database and secure session design are provisioned.

There is no Render service, FastAPI backend, external backend URL or Render blueprint in this deployment.

## Deploy

1. Connect heidif24/hardware-ai to the Vercel project.
2. Set the root directory to the repository root.
3. Use the Next.js framework preset and Node.js 20 or later.
4. Optionally add OPENAI_API_KEY as a server-side Vercel environment variable. Optionally set OPENAI_MODEL (default: gpt-4.1-mini).
5. Deploy from main.

The app works without an OpenAI key using deterministic baseline synthesis. Never expose provider credentials through NEXT_PUBLIC variables or commit secrets.

## Local development

Run npm install, then npm run dev. Open http://localhost:3000.

## Engineering integrity and release limits

The generated ZIP includes the product brief, architecture JSON, engineering report, requirements baseline, candidate functional BOM, architecture SVG, interface control document, firmware plan, mechanical design brief, verification plan, manufacturing hand-off notes, engineering release checklist and an NDA discussion template.

The current system generates concept-level planning artefacts only. It does not generate actual KiCad schematics, verified symbols or footprints, PCB layout source, ERC/DRC reports, Gerber X2, NC drill, IPC-356 netlist, pick-and-place data, assembly drawings, dimensionally accurate STEP enclosure CAD, prototype verification evidence or qualified engineering approval.

Those assets require product-specific electrical and mechanical engineering, EDA/CAD work, validation and qualified review. The package manifest and checklist explicitly identify these gaps. Never represent a generated concept dossier as an approved fabrication release.

The NDA file is a discussion template, not legal advice and not proof of an executed agreement. The user must arrange appropriate legal review and obtain signatures before confidential disclosure.

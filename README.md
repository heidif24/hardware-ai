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

The full dossier export can generate a product-specific photorealistic 3D concept image using Replicate's official `black-forest-labs/flux-1.1-pro` model. Configure `REPLICATE_API_TOKEN` in Vercel Project → Settings → Environment Variables. Optionally set `REPLICATE_IMAGE_MODEL` to another Replicate official model in `owner/model` format. The default model is metered per generated image; check the provider's current pricing before enabling it. The export includes `product_concept_render.png` only when a real render has completed. It does not substitute the architecture diagram or a placeholder. Without the token, the full-render export returns an actionable configuration error.

The render is a visual concept, not dimensionally accurate CAD, a validated enclosure, a verified circuit, or manufacturing evidence. The separate `functional_architecture.png` is a raster diagram preview.

## Product workflow

1. Enter a product brief and known engineering constraints.
2. Generate a functional architecture.
3. Review modules, interfaces, assumptions and risks.
4. Download design JSON or the engineering dossier ZIP.
5. Independently approach manufacturers and obtain a signed NDA before sharing confidential information.

## Project persistence and operational limits

The current app automatically saves the latest brief and generated architecture in the browser's local storage on that device and browser. It does not yet provide user accounts, cloud project storage, cross-device synchronisation, team workspaces or a project database. 

## Vercel-only architecture

Next.js App Router and Node.js Route Handlers run as Vercel Functions. AI provider requests are made directly from the server using HTTPS; no provider SDK or external backend service is required. ZIP dossiers are generated in the Vercel function using fflate. The current workflow does not require an external database or Render service.

## Local development

Run `npm install`, copy `.env.example` to `.env.local`, add provider keys as required, then run `npm run dev`.

## Engineering integrity and release limits

The generated ZIP includes product brief, architecture JSON, functional architecture SVG and a rendered `functional_architecture.png` preview, and (when Replicate is configured) a photorealistic `product_concept_render.png`, engineering report, requirements baseline, candidate functional BOM, interface control document, firmware and mechanical plans, verification plan, manufacturing hand-off notes, release checklist and an NDA discussion template.

The current system generates concept-level planning artefacts only. It does not generate actual KiCad schematics, verified symbols or footprints, PCB layout source, ERC/DRC reports, Gerber X2, NC drill, IPC-356 netlist, pick-and-place data, assembly drawings, dimensionally accurate STEP enclosure CAD, prototype verification evidence or qualified engineering approval. Those require product-specific engineering, CAD/EDA work, validation and qualified review.

The NDA file is a discussion template, not legal advice or proof of an executed agreement. Obtain appropriate legal review and signatures before confidential disclosure.

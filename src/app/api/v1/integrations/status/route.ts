import {NextResponse} from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const configured = (...keys: string[]) => keys.every((key) => Boolean(process.env[key]?.trim()));

export async function GET() {
  const integrations = [
    { id: "ai-gemini", name: "Google Gemini", category: "AI architecture", configured: configured("GEMINI_API_KEY"), requiredEnv: ["GEMINI_API_KEY"] },
    { id: "ai-groq", name: "Groq", category: "AI architecture", configured: configured("GROQ_API_KEY"), requiredEnv: ["GROQ_API_KEY"] },
    { id: "ai-openai", name: "OpenAI", category: "AI architecture", configured: configured("OPENAI_API_KEY"), requiredEnv: ["OPENAI_API_KEY"] },
    { id: "image-replicate", name: "Replicate FLUX", category: "Product concept rendering", configured: configured("REPLICATE_API_TOKEN"), requiredEnv: ["REPLICATE_API_TOKEN"] },
    { id: "supplier-mouser", name: "Mouser Search API", category: "Component sourcing", configured: configured("MOUSER_API_KEY"), requiredEnv: ["MOUSER_API_KEY"] },
    { id: "supplier-digikey", name: "DigiKey Product API", category: "Component sourcing", configured: configured("DIGIKEY_CLIENT_ID", "DIGIKEY_CLIENT_SECRET"), requiredEnv: ["DIGIKEY_CLIENT_ID", "DIGIKEY_CLIENT_SECRET"] },
    { id: "supplier-jlcpcb", name: "JLCPCB API", category: "PCB fabrication and ordering", configured: configured("JLCPCB_APP_ID", "JLCPCB_ACCESS_KEY", "JLCPCB_SECRET_KEY"), requiredEnv: ["JLCPCB_APP_ID", "JLCPCB_ACCESS_KEY", "JLCPCB_SECRET_KEY"], state: "approval_and_adapter_required" },
    { id: "cad-worker", name: "KiCad / CAD worker", category: "Schematic, PCB and mechanical CAD", configured: configured("CAD_WORKER_URL", "CAD_WORKER_TOKEN"), requiredEnv: ["CAD_WORKER_URL", "CAD_WORKER_TOKEN"], state: "worker_service_and_adapter_required" }
  ];
  return NextResponse.json({
    status: integrations.every((item) => item.configured) ? "configured" : "configuration_required",
    checked_at: new Date().toISOString(), integrations,
    security: { secrets_returned: false, provider_calls_made: false },
    notes: [
      "Configured means the required environment variable names have values; it does not prove that a provider credential is valid or approved.",
      "JLCPCB access is subject to vendor approval. The JLCPCB adapter is not yet implemented.",
      "The CAD worker adapter and worker service are not yet implemented. Adding its URL and token alone will not create CAD functionality."
    ]
  }, {headers: {"Cache-Control": "no-store"}});
}

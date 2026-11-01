import {NextRequest,NextResponse} from "next/server";
export const runtime="nodejs";
export const maxDuration=60;

const PLAN_PROMPT=`You are the chief engineering architect for Hardware Foundry. Convert an approved product concept into a disciplined, machine-readable engineering execution plan for electronics, PCB, firmware, mechanical CAD and verification.

Return ONLY JSON with these keys:
schema_version, engineering_status, product_summary, requirements_traceability, system_architecture, component_candidates, electrical_design, interface_design, pcb_design, firmware_design, mechanical_design, manufacturing_strategy, verification_plan, unresolved_inputs, generation_gates.

Rules:
- Do not invent component manufacturer part numbers, datasheet facts, footprints, pin numbers, voltage/current ratings, battery capacities, dimensions, tolerances, material grades, radio certifications, test results or regulatory approvals.
- A component candidate is a functional class unless exact identity is grounded by a source provided in the input. Include source_reference and evidence_excerpt only when actually supplied; otherwise set identity_status to "UNVERIFIED_FUNCTIONAL_CLASS".
- Every numerical value must be one of: user_specified, source_verified, calculated_with_method, or provisional_target. Include value_basis and method/source. Never label a provisional target as verified.
- Pin mapping, schematic netlist, PCB routing and connector pin assignments must remain blocked until exact component datasheets and verified symbol/footprint mappings are supplied.
- For a proprietary Foundry connector, define requirements and compatibility rules, not invented final pinouts or geometry. Include electrical envelope, signalling, keying, retention, sealing, mating-cycle, cable and misuse-protection requirements as unresolved where not known.
- Firmware must name the selected MCU and SDK only if supplied/verified. Otherwise provide a portable software architecture, state machine, interfaces as abstractions and target-selection gate. Do not claim a target binary.
- Mechanical CAD must use only user-specified or source-verified dimensions. If absent, produce a parametric feature plan with parameters explicitly unresolved; do not invent a manufacturing dimension.
- When and only when the exact board identity, PlatformIO board ID, framework and peripheral interface specifications are explicitly supplied or source-verified, include firmware_design.target.platformio_board, firmware_design.target.framework, firmware_design.platform and a reviewed board-specific firmware_design.application_source. Otherwise omit executable source and leave the firmware stage blocked.
- For enclosure generation, use mechanical_design.parameters with length, width, height, wall, floor and corner values. Every value must be an object containing value and value_basis; only user_specified, source_verified or calculated_with_method values are executable. Provisional targets must never enter native CAD generation.
- For a proprietary connector, use interface_design.connector_geometry with body_length, body_width, body_height, pitch, contact_diameter, cavity_depth and clearance, each with value and value_basis, plus integer pin_count and rows. Do not invent these dimensions; if absent, leave the connector CAD stage blocked. Geometry generation is not electrical qualification.
- PCB layout must not be marked routable until schematic, footprint mapping, stackup, board outline, constraints and component placements are frozen.
- Cost optimisation must compare conventional, optimised and novel candidates, state assumptions and identify what evidence is needed. Never fabricate prices or claim that a novel material is cheaper without evidence.
- Set each generation gate to READY only when all of its required inputs are present in the supplied data. Otherwise BLOCKED and enumerate missing inputs.
- Output should be detailed, product-specific and actionable. It must be safe for a downstream worker to refuse incomplete stages.`;

type Obj=Record<string,unknown>;
function jsonFromText(t:string):unknown {const s=t.trim().replace(/^```(?:json)?\s*/i,"").replace(/\s*```$/,"");try{return JSON.parse(s)}catch{const a=s.indexOf("{"),b=s.lastIndexOf("}");if(a>=0&&b>a)return JSON.parse(s.slice(a,b+1));throw new Error("AI response was not valid JSON");}}
async function generate(body:Obj):Promise<{value:unknown;provider:string}> {
 const order=(process.env.AI_PROVIDER_ORDER||"gemini,groq,openai").split(",").map(x=>x.trim());
 const errors:string[]=[];
 for(const p of order){
  const key=p==="gemini"?process.env.GEMINI_API_KEY:p==="groq"?process.env.GROQ_API_KEY:p==="openai"?process.env.OPENAI_API_KEY:undefined;
  if(!key)continue;
  try{
   let response:Response;let raw:string;
   if(p==="gemini"){
    const model=process.env.GEMINI_MODEL||"gemini-2.5-flash";
    response=await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,{method:"POST",headers:{"Content-Type":"application/json","x-goog-api-key":key},body:JSON.stringify({systemInstruction:{parts:[{text:PLAN_PROMPT}]},contents:[{role:"user",parts:[{text:JSON.stringify(body)}]}],generationConfig:{temperature:0.1,responseMimeType:"application/json"}}),signal:AbortSignal.timeout(35000)});
    if(!response.ok)throw new Error("Gemini HTTP "+response.status);const d=await response.json();raw=d.candidates?.[0]?.content?.parts?.map((x:{text?:string})=>x.text||"").join("")||"";
   }else{
    const model=p==="groq"?(process.env.GROQ_MODEL||"llama-3.3-70b-versatile"):(process.env.OPENAI_MODEL||"gpt-4.1-mini");
    const url=p==="groq"?"https://api.groq.com/openai/v1/chat/completions":"https://api.openai.com/v1/chat/completions";
    response=await fetch(url,{method:"POST",headers:{Authorization:"Bearer "+key,"Content-Type":"application/json"},body:JSON.stringify({model,temperature:0.1,response_format:{type:"json_object"},messages:[{role:"system",content:PLAN_PROMPT},{role:"user",content:JSON.stringify(body)}]}),signal:AbortSignal.timeout(35000)});
    if(!response.ok)throw new Error(p+" HTTP "+response.status);const d=await response.json();raw=d.choices?.[0]?.message?.content||"";
   }
   const value=jsonFromText(raw);if(!value||typeof value!=="object"||Array.isArray(value))throw new Error("AI plan must be a JSON object");
   return {value,provider:p};
  }catch(e){errors.push(p+": "+(e instanceof Error?e.message:"unknown error"));}
 }
 throw new Error(errors.join("; ")||"No AI provider credentials configured. Configure GEMINI_API_KEY, GROQ_API_KEY or OPENAI_API_KEY in Vercel.");
}
function validatePlan(value:unknown):{plan:Obj;missing:string[]} {
 if(!value||typeof value!=="object"||Array.isArray(value))throw new Error("Invalid engineering plan.");
 const p=value as Obj;
 const required=["system_architecture","component_candidates","electrical_design","interface_design","pcb_design","firmware_design","mechanical_design","verification_plan","generation_gates","unresolved_inputs"];
 for(const k of required)if(!(k in p))throw new Error("Engineering plan is missing "+k);
 const missing:string[]=[];
 if(!Array.isArray(p.component_candidates))throw new Error("component_candidates must be an array.");
 p.component_candidates=(p.component_candidates as unknown[]).map((item)=>{if(!item||typeof item!=="object"||Array.isArray(item))return {identity_status:"UNVERIFIED_FUNCTIONAL_CLASS",description:String(item)};const candidate={...(item as Obj)};if((candidate.part_number||candidate.manufacturer)&&(!candidate.source_reference||!candidate.evidence_excerpt)){delete candidate.part_number;delete candidate.manufacturer;candidate.identity_status="UNVERIFIED_FUNCTIONAL_CLASS";candidate.identity_note="Specific manufacturer identity removed because no supplied source evidence supports it.";}return candidate;});
 const gates=p.generation_gates;
 if(!gates||typeof gates!=="object"||Array.isArray(gates))throw new Error("generation_gates must be an object.");
 const requiredStages=["electronics","pcb","firmware","mechanical"];
 for(const stage of requiredStages){
  const existing=(gates as Obj)[stage];
  const gate=existing&&typeof existing==="object"&&!Array.isArray(existing)?existing as Obj:{};
  const missingByStage:Record<string,string[]>={
   electronics:["Verified component identities and manufacturer datasheets","Electrical ratings, pin-level design and verified symbol/footprint mapping","Engineer-reviewed schematic and ERC report"],
   pcb:["Validated schematic/netlist","Verified footprints, board outline, stackup and placement constraints","Routed PCB and DRC review"],
   firmware:["Frozen MCU/board identity and pin map","Trusted SDK, build configuration and peripheral specifications","Board-specific compile and hardware test evidence"],
   mechanical:["User-specified or source-verified dimensions and tolerances","Material/process selection and mating/interface constraints","Generated CAD geometry with dimensional and interference checks"]
  };
  // A language model cannot self-certify evidence. With no attached, independently verified engineering-source package in this request, every native stage remains blocked.
  gate.status="BLOCKED";
  gate.missing_inputs=[...new Set([...(Array.isArray(gate.missing_inputs)?gate.missing_inputs.map(String):[]),...missingByStage[stage]])];
  (gates as Obj)[stage]=gate;
  missing.push(...(gate.missing_inputs as string[]));
 }
 p.engineering_status="ENGINEERING_PLAN_READY_NATIVE_GENERATION_BLOCKED_PENDING_VERIFIED_INPUTS";
 p.unresolved_inputs=Array.isArray(p.unresolved_inputs)?p.unresolved_inputs:[];
 p.schema_version="1.0";
 return {plan:p,missing:[...new Set(missing)]};
}
export async function POST(req:NextRequest){
 try{
  const body=await req.json() as Obj;
  if(body.design_approved!==true)return NextResponse.json({detail:"Approve the product design before creating an engineering plan."},{status:409});
  if(!body.design||typeof body.design!=="object")return NextResponse.json({detail:"Approved design is required."},{status:422});
  const generated=await generate(body);const checked=validatePlan(generated.value);
  return NextResponse.json({engineering_plan:checked.plan,provider:generated.provider,missing_inputs:checked.missing,release_notice:"This plan is an AI-generated engineering proposal, not validated CAD, a verified schematic, a routed PCB or a certified design. Native generation gates must pass and qualified review remains required."});
 }catch(e){const message=e instanceof Error?e.message:"Engineering plan generation failed.";return NextResponse.json({detail:message},{status:422});}
}

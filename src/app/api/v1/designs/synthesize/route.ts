import {NextRequest,NextResponse} from "next/server";

export const runtime="nodejs";
export const maxDuration=60;

type Req={idea:string;constraints?:string;quantity?:number;target_unit_cost?:number};
type Module={id:string;name:string;purpose:string;interfaces:string[];parts:string[]};
type Design={product_name:string;summary:string;assumptions:string[];modules:Module[];risks:string[];validation_status:"concept_only";estimated_complexity:string;generation_mode:string;generation_provider?:string;generation_notice?:string};

const SYSTEM_PROMPT=`You are a principal electronics systems architect. Produce a cautious, useful first-pass functional architecture for the product brief. Return ONLY valid JSON with these keys: product_name, summary, assumptions (string array), modules (array of objects with id, name, purpose, interfaces (string array), parts (string array)), risks (string array), validation_status ("concept_only"), estimated_complexity ("LOW", "MEDIUM", or "HIGH"). Include only modules relevant to the product. Candidate parts must be functional classes, not invented manufacturer part numbers or stock claims. Do not invent electrical ratings, verified footprints, schematics, CAD, Gerbers, test results, prices or certification. Identify unknowns and engineering validation required. Do not claim fabrication readiness.`;

function fallback(r:Req):Design {
 const b=r.idea.toLowerCase();const modules:Module[]=[];
 const add=(name:string,purpose:string,parts:string[],interfaces:string[])=>modules.push({id:name.toLowerCase(),name,purpose,parts,interfaces});
 add("Power","Power conversion, protection and energy storage sized to the duty cycle.",["battery chemistry and capacity to be selected","charger / power-path controller","regulated DC-DC converter","protection and fuel-gauge circuit"],["battery bus","regulated rails"]);
 add("Processing","Central control, scheduling, firmware and peripheral coordination.",["low-power MCU with required peripheral set","non-volatile memory if required","programming and debug interface"],["I2C / SPI / UART","GPIO"]);
 if(/gps|location|tracker|cattle/.test(b))add("Sensing","Positioning and optional motion acquisition.",["GNSS receiver and matched antenna","3-axis low-power accelerometer"],["UART","I2C","RF antenna feed"]);
 else add("Sensing","Application-specific input acquisition.",["calibrated application sensor","signal conditioning / protection"],["I2C / SPI / ADC"]);
 if(/cellular|gps|tracker|remote|wireless|connected/.test(b))add("Connectivity","Communications link; regional coverage and certification need validation.",["cellular / LPWAN / Wi-Fi module selected for region","SIM/eSIM interface if cellular","RF matching and antenna"],["UART","RF","SIM"]);
 if(/display|screen|button|e-ink/.test(b))add("Interface","Local status and user controls.",["display matched to interface requirements","buttons / LEDs as needed"],["SPI / I2C","GPIO"]);
 if(/motor|valve|pump|irrigation|actuator/.test(b))add("Actuation","Protected switching or motor drive.",["rated MOSFET or motor-driver stage","transient protection","current sensing if required"],["PWM / GPIO","power output"]);
 return {product_name:r.idea.split(/\s+/).slice(0,7).join(" ").replace(/[.,]$/,""),summary:"First-pass functional architecture. Component identities, electrical sizing and manufacturability remain to be verified.",assumptions:["Operating environment, service life and ingress-protection target need specification.","Power budget and battery runtime require a quantified duty-cycle model.","Regional radio bands, EMC requirements and certification must be established.","Candidate components are functional categories, not confirmed stock or purchasable line items."],modules,risks:["No schematic capture, ERC, signal-integrity analysis or thermal simulation has been performed.","PCB layout and Gerbers must come from a verified schematic and reviewed layout.","Battery, charging, RF and enclosure safety depend on final use and target market."],validation_status:"concept_only",estimated_complexity:"MEDIUM",generation_mode:"deterministic_fallback",generation_notice:"AI providers were unavailable or returned an invalid response. A deterministic baseline architecture was generated."};
}
function validateDesign(value:unknown):Omit<Design,"generation_mode"|"generation_provider">|null {
 if(!value||typeof value!=="object")return null;const d=value as Record<string,unknown>;
 if(typeof d.product_name!=="string"||typeof d.summary!=="string"||!Array.isArray(d.modules)||d.modules.length<1||d.modules.length>20)return null;
 const modules:Module[]=[];
 for(const raw of d.modules){if(!raw||typeof raw!=="object")return null;const m=raw as Record<string,unknown>;if(typeof m.name!=="string"||typeof m.purpose!=="string")return null;
  const strings=(v:unknown)=>Array.isArray(v)?v.filter((x):x is string=>typeof x==="string").slice(0,20):[];
  modules.push({id:typeof m.id==="string"?m.id:m.name.toLowerCase().replace(/[^a-z0-9]+/g,"-"),name:m.name.slice(0,100),purpose:m.purpose.slice(0,1200),interfaces:strings(m.interfaces),parts:strings(m.parts)});
 }
 const strings=(v:unknown)=>Array.isArray(v)?v.filter((x):x is string=>typeof x==="string").slice(0,30):[];
 return {product_name:d.product_name.slice(0,180),summary:d.summary.slice(0,3000),assumptions:strings(d.assumptions),modules,risks:strings(d.risks),validation_status:"concept_only",estimated_complexity:typeof d.estimated_complexity==="string"?d.estimated_complexity.slice(0,40):"To be assessed"};
}
function extractJson(raw:string):unknown {
 const cleaned=raw.trim().replace(/^\uFEFF/,"").replace(/^```(?:json)?\s*/i,"").replace(/\s*```$/,"");
 try{return JSON.parse(cleaned)}catch{const start=cleaned.indexOf("{"),end=cleaned.lastIndexOf("}");if(start>=0&&end>start)return JSON.parse(cleaned.slice(start,end+1));throw new Error("Provider did not return valid JSON");}
}
async function askOpenAICompatible(provider:"openai"|"groq",key:string,model:string,body:Req){
 const endpoint=provider==="groq"?"https://api.groq.com/openai/v1/chat/completions":"https://api.openai.com/v1/chat/completions";
 const res=await fetch(endpoint,{method:"POST",headers:{"Authorization":`Bearer ${key}`,"Content-Type":"application/json"},body:JSON.stringify({model,temperature:0.2,response_format:{type:"json_object"},messages:[{role:"system",content:SYSTEM_PROMPT},{role:"user",content:JSON.stringify(body)}]}),signal:AbortSignal.timeout(18000)});
 if(!res.ok)throw new Error(`${provider} returned HTTP ${res.status}`);const data=await res.json();const text=data.choices?.[0]?.message?.content;if(typeof text!=="string"||!text.trim())throw new Error(`${provider} returned empty content`);return extractJson(text);
}
async function askGemini(key:string,model:string,body:Req){
 const res=await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,{method:"POST",headers:{"Content-Type":"application/json","x-goog-api-key":key},body:JSON.stringify({systemInstruction:{parts:[{text:SYSTEM_PROMPT}]},contents:[{role:"user",parts:[{text:JSON.stringify(body)}]}],generationConfig:{temperature:0.2,responseMimeType:"application/json"}}),signal:AbortSignal.timeout(18000)});
 if(!res.ok)throw new Error(`Gemini returned HTTP ${res.status}`);const data=await res.json();const text=data.candidates?.[0]?.content?.parts?.map((p:{text?:string})=>p.text||"").join("");if(typeof text!=="string"||!text.trim())throw new Error("Gemini returned empty content");return extractJson(text);
}
export async function POST(req:NextRequest){
 try{
  const body=await req.json() as Req;if(typeof body.idea!=="string"||body.idea.trim().length<8||body.idea.length>4000)return NextResponse.json({detail:"Product description must contain 8–4,000 characters."},{status:422});
  const providers=(process.env.AI_PROVIDER_ORDER||"gemini,groq,openai").split(",").map(x=>x.trim().toLowerCase()).filter((x,i,a)=>["gemini","groq","openai"].includes(x)&&a.indexOf(x)===i);
  const attempts:string[]=[];
  for(const provider of providers){
   const key=provider==="gemini"?process.env.GEMINI_API_KEY:provider==="groq"?process.env.GROQ_API_KEY:process.env.OPENAI_API_KEY;
   if(!key)continue;
   try{
    const raw=provider==="gemini"?await askGemini(key,process.env.GEMINI_MODEL||"gemini-2.5-flash",body):provider==="groq"?await askOpenAICompatible("groq",key,process.env.GROQ_MODEL||"llama-3.3-70b-versatile",body):await askOpenAICompatible("openai",key,process.env.OPENAI_MODEL||"gpt-4.1-mini",body);
    const design=validateDesign(raw);if(!design)throw new Error("Provider returned an invalid architecture structure");
    return NextResponse.json({...design,generation_mode:`${provider}_structured`,generation_provider:provider});
   }catch(error){attempts.push(provider);console.error(`Hardware Foundry ${provider} generation failed:`,error instanceof Error?error.message:"unknown error");}
  }
  const result=fallback(body);if(attempts.length)result.generation_notice=`AI generation could not be completed by: ${attempts.join(", ")}. A deterministic baseline was generated instead.`;else result.generation_notice="No AI provider credentials are configured. Add GEMINI_API_KEY, GROQ_API_KEY or OPENAI_API_KEY in Vercel to enable AI-assisted architecture generation.";
  return NextResponse.json(result);
 }catch{return NextResponse.json({detail:"Invalid synthesis request."},{status:400});}
}

import json,os
from openai import OpenAI
from .models import SynthesisRequest,DesignResponse
SYSTEM="""You are a principal electronics systems architect. Turn the brief into a cautious concept architecture. Decompose into Power, Processing, Sensing, Connectivity, Interface and Actuation as needed. Never invent distributor stock, prices, LCSC numbers, verified footprints, electrical ratings, Gerbers or pick-and-place data. Parts are candidate classes, not verified items. Return JSON keys product_name, summary, assumptions, modules [{id,name,purpose,interfaces,parts}], risks, validation_status='concept_only', estimated_complexity='LOW|MEDIUM|HIGH'. Include meaningful engineering and safety risks."""
def baseline(r):
 b=r.idea.lower();mods=[]
 def add(n,p,parts,interfaces):mods.append(dict(id=n.lower(),name=n,purpose=p,parts=parts,interfaces=interfaces,status="concept"))
 add("Power","Power conversion, protection and energy storage sized to the duty cycle.",["battery chemistry and capacity to be selected","charger / power-path controller","regulated DC-DC converter","protection and fuel-gauge circuit"],["battery bus","regulated rails"])
 add("Processing","Central control, scheduling, firmware and peripheral coordination.",["low-power MCU with required peripheral set","non-volatile memory if required","programming and debug interface"],["I2C / SPI / UART","GPIO"])
 if any(x in b for x in ["gps","location","tracker","cattle"]):add("Sensing","Positioning and optional motion acquisition.",["GNSS receiver and matched antenna","3-axis low-power accelerometer"],["UART","I2C","RF antenna feed"])
 else:add("Sensing","Application-specific input acquisition.",["calibrated application sensor","signal conditioning / protection"],["I2C / SPI / ADC"])
 if any(x in b for x in ["cellular","gps","tracker","remote","wireless","connected"]):add("Connectivity","Communications link; regional coverage and certification need validation.",["cellular / LPWAN / Wi-Fi module selected for region","SIM/eSIM interface if cellular","RF matching and antenna"],["UART","RF","SIM"])
 if any(x in b for x in ["display","screen","button","e-ink"]):add("Interface","Local status and user controls.",["display matched to interface requirements","buttons / LEDs as needed"],["SPI / I2C","GPIO"])
 if any(x in b for x in ["motor","valve","pump","irrigation","actuator"]):add("Actuation","Protected switching or motor drive.",["rated MOSFET or motor-driver stage","transient protection","current sensing if required"],["PWM / GPIO","power output"])
 return dict(product_name=" ".join(r.idea.split()[:7]).strip(".,"),summary="First-pass functional architecture. Component identities, electrical sizing and manufacturability remain to be verified.",assumptions=["Operating environment, service life and ingress-protection target need specification.","Power budget and battery runtime require a quantified duty-cycle model.","Regional radio bands, EMC requirements and certification must be established.","Candidate components are functional categories, not confirmed stock or purchasable line items."],modules=mods,risks=["No schematic capture, ERC, signal-integrity analysis or thermal simulation has been performed.","PCB layout and Gerbers must come from a verified schematic and reviewed layout.","Battery, charging, RF and enclosure safety depend on final use and target market."],validation_status="concept_only",estimated_complexity="MEDIUM")
async def synthesize(r):
 key=os.getenv("OPENAI_API_KEY")
 if not key:return DesignResponse.model_validate(baseline(r))
 try:
  c=OpenAI(api_key=key);o=c.chat.completions.create(model=os.getenv("OPENAI_MODEL","gpt-4.1-mini"),temperature=.2,response_format={"type":"json_object"},messages=[{"role":"system","content":SYSTEM},{"role":"user","content":json.dumps(r.model_dump())}],timeout=45);d=json.loads(o.choices[0].message.content or "{}");d["validation_status"]="concept_only";return DesignResponse.model_validate(d)
 except Exception:return DesignResponse.model_validate(baseline(r))

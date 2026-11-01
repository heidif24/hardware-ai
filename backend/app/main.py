import csv,io,json,zipfile,os
from fastapi import FastAPI,HTTPException,Depends,Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse,Response
from pydantic import BaseModel,EmailStr,Field
from sqlalchemy.orm import Session
from .models import SynthesisRequest
from .engine import synthesize
from .db import get_db,User,Project
from .security import hash_password,verify_password,create_token,current_user
from .integrations import search_components,generate_product_visual
app=FastAPI(title="Hardware Foundry API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in os.getenv("FRONTEND_ORIGINS","http://localhost:3000").split(",") if x.strip()],allow_credentials=True,allow_methods=["GET","POST","PUT","DELETE"],allow_headers=["*"])
class Credentials(BaseModel):email:EmailStr;password:str=Field(min_length=10,max_length=128)
class ProjectInput(BaseModel):name:str=Field(min_length=1,max_length=180);brief:str=Field(min_length=8,max_length=4000);design:dict
class VisualInput(BaseModel):brief:str=Field(min_length=8,max_length=4000);design:dict
@app.get("/health")
def health():return {"status":"ok","service":"hardware-foundry-api","capabilities":{"supplier_search":bool(os.getenv("MOUSER_API_KEY") or os.getenv("DIGIKEY_CLIENT_ID")),"visual_generation":bool(os.getenv("REPLICATE_API_TOKEN")),"persistent_projects":True}}
@app.post("/api/v1/designs/synthesize")
async def create_design(req:SynthesisRequest):
 try:return (await synthesize(req)).model_dump()
 except Exception as e:raise HTTPException(status_code=422,detail=str(e))
@app.post("/api/v1/auth/register")
def register(data:Credentials,db:Session=Depends(get_db)):
 email=data.email.lower()
 if db.query(User).filter(User.email==email).first():raise HTTPException(409,"An account with this email already exists")
 user=User(email=email,password_hash=hash_password(data.password));db.add(user);db.commit();db.refresh(user)
 return {"access_token":create_token(user.id),"token_type":"bearer","user":{"id":user.id,"email":user.email}}
@app.post("/api/v1/auth/login")
def login(data:Credentials,db:Session=Depends(get_db)):
 user=db.query(User).filter(User.email==data.email.lower()).first()
 if not user or not verify_password(data.password,user.password_hash):raise HTTPException(401,"Email or password is incorrect")
 return {"access_token":create_token(user.id),"token_type":"bearer","user":{"id":user.id,"email":user.email}}
@app.get("/api/v1/auth/me")
def me(user:User=Depends(current_user)):return {"id":user.id,"email":user.email}
@app.get("/api/v1/projects")
def list_projects(db:Session=Depends(get_db),user:User=Depends(current_user)):
 return [{"id":p.id,"name":p.name,"brief":p.brief,"design":json.loads(p.design_json),"updated_at":p.updated_at.isoformat()} for p in db.query(Project).filter(Project.owner_id==user.id).order_by(Project.updated_at.desc()).all()]
@app.post("/api/v1/projects")
def save_project(data:ProjectInput,db:Session=Depends(get_db),user:User=Depends(current_user)):
 p=Project(owner_id=user.id,name=data.name,brief=data.brief,design_json=json.dumps(data.design));db.add(p);db.commit();db.refresh(p)
 return {"id":p.id,"name":p.name,"brief":p.brief,"design":data.design}
@app.delete("/api/v1/projects/{project_id}")
def delete_project(project_id:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
 p=db.query(Project).filter(Project.id==project_id,Project.owner_id==user.id).first()
 if not p:raise HTTPException(404,"Project not found")
 db.delete(p);db.commit();return {"deleted":True}
@app.get("/api/v1/components/search")
async def components(q:str=Query(min_length=2,max_length=120),limit:int=8):
 if len(q)>120:raise HTTPException(422,"Search query is too long")
 return await search_components(q,max(1,min(limit,20)))
@app.post("/api/v1/visuals/render")
async def render_visual(data:VisualInput):
 try:
  image=await generate_product_visual(data.brief,data.design)
  return Response(content=image,media_type="image/png",headers={"Content-Disposition":"attachment; filename=hardware-foundry-product-concept.png","Cache-Control":"no-store"})
 except RuntimeError as e:raise HTTPException(503,str(e))
 except Exception as e:raise HTTPException(502,"Image generation provider failed: "+str(e)[:180])
@app.post("/api/v1/designs/production-bundle")
async def production_bundle(payload:dict):
 design=payload.get("design")
 if not isinstance(design,dict) or not design.get("modules"):raise HTTPException(400,"A generated design with modules is required.")
 mem=io.BytesIO()
 with zipfile.ZipFile(mem,"w",zipfile.ZIP_DEFLATED) as z:
  z.writestr("design_specification.json",json.dumps(payload,indent=2));out=io.StringIO();w=csv.writer(out);w.writerow(["Module","Function","Candidate part class","Status"])
  for m in design.get("modules",[]):
   for p in m.get("parts",[]):w.writerow([m.get("name"),m.get("purpose"),p,"UNVERIFIED_CANDIDATE"])
  z.writestr("candidate_bom.csv",out.getvalue())
  svg=["<svg xmlns='http://www.w3.org/2000/svg' width='1000' height='"+str(190+len(design.get('modules',[]))*116)+"' viewBox='0 0 1000 "+str(190+len(design.get('modules',[]))*116)+"'>","<rect width='100%' height='100%' fill='#090f10'/>","<text x='70' y='55' fill='#b7f36b' font-family='Arial' font-size='13'>HARDWARE FOUNDRY / FUNCTIONAL ARCHITECTURE</text>","<text x='70' y='105' fill='white' font-family='Arial' font-size='28'>"+str(design.get('product_name','Product'))+"</text>"]
  for i,m in enumerate(design.get("modules",[])):
   y=150+i*116;name=str(m.get("name","Module")).replace("&","&amp;").replace("<","&lt;");purpose=str(m.get("purpose","")).replace("&","&amp;").replace("<","&lt;")
   svg.append("<rect x='70' y='"+str(y)+"' width='860' height='86' rx='14' fill='#111719' stroke='#52634a'/>");svg.append("<text x='100' y='"+str(y+32)+"' fill='#b7f36b' font-family='Arial' font-size='20'>"+name+"</text>");svg.append("<text x='100' y='"+str(y+59)+"' fill='#d6dfd8' font-family='Arial' font-size='14'>"+purpose[:105]+"</text>")
  svg.append("</svg>");z.writestr("functional_architecture.svg","".join(svg))
  checklist=io.StringIO();cw=csv.writer(checklist);cw.writerow(["Engineering gate","Required evidence","Status"])
  for item,evidence in [("Electrical requirements","Voltage/current ranges, interfaces, environment, safety requirements"),("Schematic capture","Native EDA schematic and annotated netlist"),("Component verification","Manufacturer part numbers, datasheets, lifecycle and stock confirmation"),("Footprint verification","Datasheet-matched land patterns and 3D package models"),("PCB layout","Board outline, stack-up, copper weights, clearances and routing"),("ERC","Electrical rules check report with no unresolved critical errors"),("DRC","PCB design rules report with no unresolved critical errors"),("Fabrication outputs","Gerber X2, NC drill, IPC netlist and stack-up drawing"),("Assembly outputs","Centroid/pick-and-place, assembly drawing and approved BOM"),("Prototype validation","Bring-up, functional, thermal, EMC and environmental test evidence")]:cw.writerow([item,evidence,"NOT COMPLETED / ENGINEER SIGN-OFF REQUIRED"])
  z.writestr("engineering_release_checklist.csv",checklist.getvalue())
  quote={"product":design.get("product_name"),"requested_quantity":payload.get("quantity",100),"target_unit_cost_usd":payload.get("target_unit_cost"),"board_dimensions_mm":"TO BE ENGINEERED","layers":"TO BE ENGINEERED","surface_finish":"Factory recommendation after design review","assembly":"SMT/PCBA quote requested","status":"RFQ_PREPARATION_ONLY","required_vendor_review":["Gerber and drill files from validated PCB CAD","BOM with manufacturer part numbers and approved alternates","Centroid / pick-and-place file from validated PCB layout","Board stack-up, dimensions, thickness and copper weight","Assembly drawings, test plan and programming requirements"]}
  z.writestr("factory_RFQ_request.json",json.dumps(quote,indent=2));z.writestr("FACTORY_HANDOFF_README.txt","HARDWARE FOUNDRY — ENGINEERING CONCEPT / RFQ PREPARATION\n\nThis package is not a fabrication release. It does not contain Gerber, drill, IPC netlist, verified footprints, pick-and-place coordinates, assembly drawings or validated electrical design. Do not order PCBs from this concept package. A qualified hardware engineer must complete schematic capture, component verification, PCB layout, ERC/DRC, stack-up and manufacturing review. Submit the resulting verified files to JLCPCB or PCBWay for a formal quotation.\n")
 mem.seek(0);return StreamingResponse(mem,media_type="application/zip",headers={"Content-Disposition":"attachment; filename=hardware-foundry-factory-RFQ-preparation.zip"})

import csv,io,json,zipfile
from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from .models import SynthesisRequest
from .engine import synthesize
app=FastAPI(title="Hardware Foundry API",version="0.1.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:3000"],allow_credentials=True,allow_methods=["GET","POST"],allow_headers=["*"])
@app.get("/health")
def health():return {"status":"ok","service":"hardware-foundry-api","mode":"concept_engine"}
@app.post("/api/v1/designs/synthesize")
async def create_design(req:SynthesisRequest):
 try:return (await synthesize(req)).model_dump()
 except Exception as e:raise HTTPException(status_code=422,detail=str(e))
@app.post("/api/v1/designs/production-bundle")
async def production_bundle(payload:dict):
 design=payload.get("design")
 if not isinstance(design,dict) or not design.get("modules"):raise HTTPException(status_code=400,detail="A generated design with modules is required.")
 mem=io.BytesIO()
 with zipfile.ZipFile(mem,"w",zipfile.ZIP_DEFLATED) as z:
  z.writestr("design_specification.json",json.dumps(payload,indent=2));out=io.StringIO();w=csv.writer(out);w.writerow(["Module","Function","Candidate part class","Status"])
  for m in design.get("modules",[]):
   for p in m.get("parts",[]):w.writerow([m.get("name"),m.get("purpose"),p,"UNVERIFIED_CANDIDATE"])
  z.writestr("candidate_bom.csv",out.getvalue());z.writestr("MANUFACTURING_STATUS.txt","CONCEPT PACKAGE ONLY. No Gerber, drill, verified footprint, centroid or pick-and-place data is included. Create these from an electrically validated PCB design and review before fabrication.\n")
 mem.seek(0);return StreamingResponse(mem,media_type="application/zip",headers={"Content-Disposition":"attachment; filename=hardware-foundry-concept-bundle.zip"})

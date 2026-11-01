import json, os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from .models import SynthesisRequest
from .engine import synthesize
from .db import get_db, User, Project
from .security import hash_password, verify_password, create_token, current_user
from .integrations import generate_product_visual
from .dossier import build_dossier

app = FastAPI(title="Hardware Foundry API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"]
)

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    brief: str = Field(min_length=8, max_length=4000)
    design: dict

class VisualInput(BaseModel):
    brief: str = Field(min_length=8, max_length=4000)
    design: dict

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "hardware-foundry-api",
        "capabilities": {
            "concept_synthesis": True,
            "ai_synthesis": bool(os.getenv("OPENAI_API_KEY")),
            "product_visual_generation": bool(os.getenv("OPENAI_API_KEY") or os.getenv("REPLICATE_API_TOKEN")),
            "persistent_projects": True,
            "vendor_neutral_dossier": True,
            "supplier_pricing": False
        }
    }

@app.post("/api/v1/designs/synthesize")
async def create_design(request: SynthesisRequest):
    try:
        return (await synthesize(request)).model_dump()
    except Exception:
        raise HTTPException(status_code=422, detail="The product brief could not be converted into an engineering concept. Review the brief and try again.")

@app.post("/api/v1/auth/register")
def register(data: Credentials, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": {"id": user.id, "email": user.email}}

@app.post("/api/v1/auth/login")
def login(data: Credentials, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect")
    return {"access_token": create_token(user.id), "token_type": "bearer", "user": {"id": user.id, "email": user.email}}

@app.get("/api/v1/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email}

@app.get("/api/v1/projects")
def list_projects(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [
        {"id": project.id, "name": project.name, "brief": project.brief, "design": json.loads(project.design_json), "updated_at": project.updated_at.isoformat()}
        for project in db.query(Project).filter(Project.owner_id == user.id).order_by(Project.updated_at.desc()).all()
    ]

@app.post("/api/v1/projects")
def save_project(data: ProjectInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project = Project(owner_id=user.id, name=data.name, brief=data.brief, design_json=json.dumps(data.design))
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "name": project.name, "brief": project.brief, "design": data.design}

@app.delete("/api/v1/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project = db.query(Project).filter(Project.id == project_id, Project.owner_id == user.id).first()
    if not project:
        raise HTTPException(404, "Project not found")
    db.delete(project)
    db.commit()
    return {"deleted": True}

@app.post("/api/v1/visuals/render")
async def render_visual(data: VisualInput):
    try:
        image = await generate_product_visual(data.brief, data.design)
        return Response(
            content=image,
            media_type="image/png",
            headers={"Content-Disposition": "attachment; filename=hardware-foundry-product-concept.png", "Cache-Control": "no-store"}
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=502, detail="The image provider failed to generate a product concept. Check its backend configuration.")

@app.post("/api/v1/designs/manufacturing-package")
async def manufacturing_package(payload: dict):
    try:
        archive, filename = build_dossier(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"}
    )

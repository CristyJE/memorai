"""
app/main.py

Azure App Service entrypoint — FastAPI family memoir portal.
Serves the family-facing web interface for reading, sharing,
and downloading the compiled memoir.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel

from services.cosmos_db import CosmosDBService
from services.ai_vision import AIVisionService
from services.translator import TranslatorService

# ── App setup ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise shared service clients
    app.state.cosmos = CosmosDBService()
    app.state.vision = AIVisionService()
    app.state.translator = TranslatorService()
    yield
    # Shutdown: nothing to tear down for these stateless clients

app = FastAPI(
    title="MemorAI — Family Portal",
    description="Preserve and share your loved one's life story.",
    version="1.0.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory="templates")


# ── Request models ─────────────────────────────────────────────────────────────

class ProfileCreate(BaseModel):
    senior_id: str
    name: str
    age: int
    language: str = "Filipino"
    family_email: str


class MemoirGenerateRequest(BaseModel):
    senior_id: str
    language: str = "en"


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("memoir.html", {"request": request})


@app.post("/api/profile")
async def create_profile(request: Request, profile: ProfileCreate):
    """Register a new senior and create their interview profile."""
    cosmos: CosmosDBService = request.app.state.cosmos
    existing = await cosmos.get_profile(profile.senior_id)
    if existing:
        raise HTTPException(status_code=409, detail="Profile already exists.")

    created = await cosmos.create_profile(profile.model_dump())
    return JSONResponse({"message": "Profile created.", "profile": created})


@app.get("/api/profile/{senior_id}")
async def get_profile(request: Request, senior_id: str):
    """Retrieve a senior's profile and interview progress."""
    cosmos: CosmosDBService = request.app.state.cosmos
    profile = await cosmos.get_profile(senior_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return profile


@app.get("/api/memoir/{senior_id}")
async def get_memoir(request: Request, senior_id: str):
    """Retrieve the compiled memoir for a senior."""
    cosmos: CosmosDBService = request.app.state.cosmos
    memoir = await cosmos.get_memoir(senior_id)
    if not memoir:
        raise HTTPException(
            status_code=404,
            detail="Memoir not yet compiled. Complete more interview sessions first.",
        )
    return memoir


@app.post("/api/memoir/{senior_id}/generate")
async def trigger_memoir_generation(
    request: Request,
    senior_id: str,
    body: MemoirGenerateRequest,
):
    """
    Queue a memoir compilation job.
    In production this publishes to Azure Storage Queue;
    the memoir_generator Function picks it up asynchronously.
    """
    import json
    from azure.storage.blob import BlobServiceClient

    # Publish to queue (simplified — use azure-storage-queue in production)
    payload = json.dumps({
        "senior_id": senior_id,
        "language": body.language,
    })
    # TODO: publish payload to Azure Storage Queue 'memoir-jobs'
    # queue_client.send_message(payload)

    return JSONResponse({
        "message": "Memoir compilation queued.",
        "senior_id": senior_id,
        "estimated_minutes": 5,
    })


@app.post("/api/photos/upload")
async def upload_photo(
    request: Request,
    senior_id: str,
    file: UploadFile = File(...),
):
    """
    Upload and enrich a family photo.
    Azure AI Vision analyses the image and tags it with era, faces, and scene.
    """
    vision: AIVisionService = request.app.state.vision
    contents = await file.read()

    enrichment = await vision.analyse_photo(
        image_bytes=contents,
        senior_id=senior_id,
        filename=file.filename,
    )

    return JSONResponse({
        "message": "Photo uploaded and enriched.",
        "enrichment": enrichment,
    })


@app.get("/health")
async def health():
    return {"status": "ok", "service": "MemorAI Family Portal"}

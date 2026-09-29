from pathlib import Path
from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.database import get_db
from backend.app.api.v1 import v1_router
from backend.app.api.v1.health import get_data_health

app = FastAPI(
    title="COMEDK Compass - Ingestion & Foundation API",
    description="Production-grade COMEDK engineering counselling data foundation",
    version=settings.PARSER_VERSION,
)

# CORS middleware for local frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(v1_router, prefix="/api/v1")

# Jinja template setup for internal admin data health page
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

@app.get("/data-health", response_class=HTMLResponse, tags=["Admin UI"])
@app.get("/admin/data-health", response_class=HTMLResponse, tags=["Admin UI"])
def view_data_health(request: Request, db: Session = Depends(get_db)):
    health_data = get_data_health(db)
    template = jinja_env.get_template("data_health.html")
    html_content = template.render(request=request, health=health_data)
    return HTMLResponse(content=html_content)

@app.get("/")
def root():
    return {
        "service": "COMEDK Compass Data Foundation",
        "version": settings.PARSER_VERSION,
        "docs_url": "/docs",
        "data_health_url": "/data-health",
        "api_v1": "/api/v1"
    }

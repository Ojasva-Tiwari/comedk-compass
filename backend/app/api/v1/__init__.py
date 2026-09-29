from fastapi import APIRouter
from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.colleges import router as colleges_router
from backend.app.api.v1.branches import router as branches_router
from backend.app.api.v1.sources import router as sources_router
from backend.app.api.v1.cutoffs import router as cutoffs_router
from backend.app.api.v1.seats import router as seats_router
from backend.app.api.v1.fees import router as fees_router

v1_router = APIRouter()
v1_router.include_router(health_router)
v1_router.include_router(colleges_router)
v1_router.include_router(branches_router)
v1_router.include_router(sources_router)
v1_router.include_router(cutoffs_router)
v1_router.include_router(seats_router)
v1_router.include_router(fees_router)

from fastapi import APIRouter

from backend.app.api.routers import auth, calendar, charts, imports, lots, master_data, materials, ratings, settings, sinottico


api_router = APIRouter(prefix="/api")


@api_router.get("/health")
def health():
    return {"ok": True}


api_router.include_router(auth.router)
api_router.include_router(materials.router)
api_router.include_router(calendar.router)
api_router.include_router(charts.router)
api_router.include_router(ratings.router)
api_router.include_router(lots.router)
api_router.include_router(sinottico.router)
api_router.include_router(imports.router)
api_router.include_router(master_data.router)
api_router.include_router(settings.router)

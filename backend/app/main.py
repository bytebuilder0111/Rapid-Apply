from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.analysis.router import router as analysis_router
from app.auth.router import router as auth_router
from app.config import settings
from app.errors import register_exception_handlers
from app.integrations.router import router as integrations_router
from app.profiles.router import router as profiles_router
from app.sheets.router import router as sheets_router
from app.users.admin_router import router as admin_router

app = FastAPI(title="JD Analyzer API", version="0.1.0")

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(profiles_router, prefix="/api/v1/profiles", tags=["profiles"])
app.include_router(integrations_router, prefix="/api/v1/integrations", tags=["integrations"])
app.include_router(analysis_router, prefix="/api/v1/analyses", tags=["analysis"])
app.include_router(sheets_router, prefix="/api/v1/sheet-configs", tags=["sheets"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health")
async def api_health() -> dict[str, str]:
    return {"status": "ok"}

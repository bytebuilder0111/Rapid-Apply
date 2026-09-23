from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import settings
from app.errors import register_exception_handlers
from app.profiles.router import router as profiles_router
from app.tech_stacks.router import admin_router as tech_stacks_admin_router
from app.tech_stacks.router import router as tech_stacks_router
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
app.include_router(tech_stacks_router, prefix="/api/v1/tech-stacks", tags=["tech-stacks"])
app.include_router(
    tech_stacks_admin_router, prefix="/api/v1/admin/tech-stacks", tags=["admin", "tech-stacks"]
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health")
async def api_health() -> dict[str, str]:
    return {"status": "ok"}

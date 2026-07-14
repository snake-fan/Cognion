from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_database
from .routes import router
from .services.config import CORS_ALLOWED_ORIGINS, IS_PRODUCTION, JWT_SECRET, SMTP_HOST

app = FastAPI(
    title="Cognion API",
    version="0.1.0",
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def on_startup() -> None:
    if IS_PRODUCTION:
        if len(JWT_SECRET) < 32 or JWT_SECRET == "development-only-change-me":
            raise RuntimeError("A strong JWT_SECRET is required in production")
        if not SMTP_HOST:
            raise RuntimeError("SMTP_HOST is required in production")
        if not CORS_ALLOWED_ORIGINS or "*" in CORS_ALLOWED_ORIGINS:
            raise RuntimeError("Explicit CORS_ALLOWED_ORIGINS are required in production")
    init_database()


app.include_router(router, prefix="/api")

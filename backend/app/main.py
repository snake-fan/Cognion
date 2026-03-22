from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import router

app = FastAPI(title="Cognion API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(router, prefix="/api")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.games import router as games_router
from app.config import settings

app = FastAPI(title="Canasta Online")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(games_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

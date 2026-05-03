import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.db_models.database import create_db_and_tables

from backend.api.collections import router as collections_router
from backend.api.folders import router as folders_router
from backend.api.images import router as images_router
from backend.api.index import router as index_router
from backend.api.people import router as people_router
from backend.api.saved_searches import router as saved_searches_router
from backend.api.search import router as search_router
from backend.api.settings import router as settings_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    create_db_and_tables()
    yield

app = FastAPI(
    title="Glimpse API",
    description="API for Glimpse photo management",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware if frontend runs on a different port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update with frontend origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(collections_router, prefix="/api")
app.include_router(folders_router, prefix="/api")
app.include_router(images_router, prefix="/api")
app.include_router(index_router, prefix="/api")
app.include_router(people_router, prefix="/api")
app.include_router(saved_searches_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(settings_router, prefix="/api")

@app.get("/")
def root():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

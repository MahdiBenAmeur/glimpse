from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.db_models.database import create_db_and_tables

from backend.api.collections import router as collections_router
from backend.api.folders import router as folders_router
from backend.api.images import router as images_router
from backend.api.people import router as people_router

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
app.include_router(people_router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to Glimpse API"}

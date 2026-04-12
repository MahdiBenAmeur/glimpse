from .collections import router as collections_router
from .folders import router as folders_router
from .images import router as images_router
from .people import router as people_router

__all__ = [
    "collections_router",
    "folders_router",
    "images_router",
    "people_router"
]

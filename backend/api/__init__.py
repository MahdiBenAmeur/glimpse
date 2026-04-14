from .collections import router as collections_router
from .folders import router as folders_router
from .images import router as images_router
from .index import router as index_router
from .people import router as people_router
from .saved_searches import router as saved_searches_router
from .search import router as search_router

__all__ = [
    "collections_router",
    "folders_router",
    "images_router",
    "index_router",
    "people_router",
    "saved_searches_router",
    "search_router",
]

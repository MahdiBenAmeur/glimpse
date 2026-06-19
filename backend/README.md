# Glimpse backend

FastAPI application powering the Glimpse media search engine.

## Structure

- `api/` — route modules for search, indexing, folders, people, collections, images, saved searches, settings
- `core/` — search engine, indexing pipeline, model wrappers (CLIP / SigLIP), face detection and clustering, unified FAISS store
- `db_models/` — SQLModel table definitions for folders, collections, saved searches
- `schemas/` — request/response schemas used by the API layer
- `services/` — application services for folders, imports, media metadata, thumbnails, collections, saved searches, library state
- `utils/` — helpers for image preparation, path normalization, FAISS store utilities, video processing
- `tests/` — test coverage
- `data/` — runtime data (vector stores, cached models, imported files, thumbnails)

## Key concepts

- **Unified vector store**: images and video keyframes share a single FAISS index, model-scoped by namespace
- **Video keyframes**: PySceneDetect splits videos into scenes; the midpoint frame of each scene is extracted (PyAV), embedded with the same image model, and stored alongside images with scene timestamp metadata
- **Search**: queries the entire unified index (no early cutoff), deduplicates (best keyframe per video, unique path per image), filters by media type, paginates
- **Faces**: YOLOv11n detection, ViT-S embedding, DBSCAN clustering into person identities

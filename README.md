# Glimpse

Glimpse is a local-first desktop app for exploring a personal image and video library with semantic search, image-to-image similarity, face clustering, favorites, collections, and saved searches. The goal of the app is to let you find photos and videos by meaning instead of filenames alone while keeping indexing, metadata, thumbnails, and model inference on your own machine. Your data never leaves your machine.

## What Glimpse does

- indexes local image and video folders and optionally imported files
- builds embeddings with a selectable vision-language model
- detects faces and groups them into people clusters
- lets you search by text, by similar image, by video scene, and with people/date/folder filters
- shows the exact timestamp of the matching scene within a video result
- keeps lightweight organization features such as favorites, collections, and saved searches

## Setup

### Prerequisites

- Python 3
- Node.js and npm

### Install dependencies

```bash
pip install -r requirements.txt
cd glimpse-front
npm install
cd ..
```

Note: `requirements.txt` installs the CPU version of PyTorch by default. If you want GPU acceleration, install a PyTorch GPU build that matches your CUDA/runtime setup after installing the requirements.

### Electron
if you want to use electron to lanch as a desktop app

```bash
cd electron
npm install
cd ..
```

## Launch

### Run pieces separately

Backend:

```bash
python server.py
```

Frontend:

```bash
cd glimpse-front
npm run dev
```

### directly through Electron

Run the desktop app through Electron:

```bash
cd electron
npx electron .
```

Electron starts the FastAPI backend, waits for it on `http://127.0.0.1:8000`, starts the Vite frontend on `http://localhost:8080`, and then opens the desktop window.


If this is the first time you use the app, you will also need to download and activate one of the supported embedding models from the onboarding flow before indexing.


## Project structure

### Top level

- `server.py`: FastAPI application entry point used by both direct backend runs and Electron
- `backend/`: backend API, indexing, search, models, state management, and tests
- `glimpse-front/`: React + Vite frontend
- `electron/`: desktop launcher that boots backend and frontend, then opens the app window
- `scripts/`: maintenance and inspection scripts for local data and clustering analysis
- `test_images/`: sample images for manual testing
- `requirements.txt`: root Python dependency file for the backend/runtime

### Backend

- `backend/api/`: FastAPI route modules for indexing, search, folders, people, collections, images, and saved searches
- `backend/core/`: core search and indexing logic, including image embedding, face detection, face clustering, and vector store orchestration
- `backend/core/indexing/index.py`: the main indexing pipeline that prepares images, loads models, writes embeddings, and finalizes face and person stores
- `backend/core/search/search.py`: the semantic search engine that runs text and image similarity search, applies filters, and ranks results
- `backend/core/models/vision_language/`: model wrappers for CLIP and SigLIP-based image/text embedding
- `backend/core/models/faces/`: face detection, face embedding, and person-clustering store logic
- `backend/db_models/`: SQLModel table definitions and database setup
- `backend/schemas/`: request and response schemas used by the API layer
- `backend/services/`: application services for folders, imports, media metadata, thumbnails, collections, saved searches, and library state
- `backend/utils/`: lower-level helpers for image preparation, path normalization, and FAISS store utilities
- `backend/tests/`: backend test coverage
- configured app data/cache directories: generated runtime data such as vector stores, cached models, imported files, and thumbnails

### Frontend

- `glimpse-front/src/pages/`: main screens such as onboarding, search, people, collections, saved searches, index manager, and settings
- `glimpse-front/src/components/`: shared UI, layout, search widgets, and image viewer components
- `glimpse-front/src/contexts/`: app-wide state management for onboarding, models, indexing, and search results
- `glimpse-front/src/lib/`: API client and shared frontend utilities
- `glimpse-front/public/`: static assets served by Vite


## How the pipeline works

1. You choose an active embedding model, then add folders or import files into the app-managed library.
2. The index job scans those folders, finds supported image and video paths, normalizes paths, and captures a `created_at` value from metadata or filesystem timestamps.
3. For **images**: the vision-language model embeds each batch and writes the vectors to a unified FAISS store alongside per-file metadata (`file_path`, `created_at`, etc.).
4. For **videos**: scene detection (PySceneDetect) splits each video into shots. The midpoint frame of each scene is extracted (PyAV), embedded with the same image model, and written into the **same unified FAISS store** with `media_type: "video"`, the source `video_id`, the precise scene midpoint timestamp, and keyframe position metadata. A single video may produce multiple keyframe vectors.
5. If face detection is enabled, the face pipeline runs on images: YOLO detects boxes, crops are embedded by the face model, and every detected face is written into the face FAISS store with its source image path, face box, confidence, and quality score.
6. After face vectors are written, the app reclusters all indexed faces with DBSCAN to rebuild person identities. Each person record stores a centroid, the list of source image paths and face boxes, weighted quality data, and a small set of top exemplar faces for previews.
7. The unified image+video store, face store, and person store are persisted under `backend/data`. Folder scan stats are updated in SQLite. Thumbnail files are generated lazily and cached on first request.
8. **Text search** embeds the query with the currently active model, searches the **entire unified FAISS index** (every item is ranked by score — no early cutoff), filters by media type ("all", "image", or "video"), deduplicates (best keyframe per video, unique path per image), and paginates results. Video results include the exact scene timestamp and keyframe position.
9. Image-to-image search embeds the query image with the same active model and searches the unified store directly. Face-photo search embeds detected query faces and matches them against the face store, then folds those matches back into results.
10. The API enriches final results with thumbnail URLs, dimensions, display dates, favorites, collections, and people labels before returning them to the frontend.


### Desktop shell and scripts

- `scripts/reset_library_data.py`: clears index, SQLite, and state files while preserving downloaded models

## Development notes

- The app is designed around local file access and local inference.
- Search quality depends on indexing with the currently active model. Switching models triggers a rebuild so vector dimensions and checkpoints stay consistent.
- Model download is separate from model activation. The first download requires internet access because checkpoints are pulled through Hugging Face.

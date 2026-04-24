# Glimpse

Glimpse is a local-first desktop app for exploring a personal image library with semantic search, image-to-image similarity, face clustering, favorites, collections, and saved searches. The goal of the app is to let you find photos by meaning instead of filenames alone while keeping indexing, metadata, thumbnails, and model inference on your own machine. Your data never leaves your machine.

## What Glimpse does

- indexes local image folders and optionally imported photos
- builds image embeddings with a selectable vision-language model
- detects faces and groups them into people clusters
- lets you search by text, by similar image, and with people/date/folder filters
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
if you want to use electron to lanch as a desktop app

```bash
cd electron
npm install
cd ..
```

### Optional virtual environment

Electron looks for Python in this order:

1. `BACKEND_PYTHON`
2. `desktopvenv/Scripts/python.exe`
3. the current `VIRTUAL_ENV`
4. `python` on `PATH`

If you want Electron to automatically use a project-local interpreter, create a virtual environment at `desktopvenv`.

## Launch

### Recommended

Run the desktop app through Electron:

```bash
cd electron
npx electron .
```

Electron starts the FastAPI backend, waits for it on `http://127.0.0.1:8000`, starts the Vite frontend on `http://localhost:8080`, and then opens the desktop window.

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

If this is the first time you use the app, you will also need to download and activate one of the supported embedding models from the onboarding flow before indexing.

## How the pipeline works

1. You choose an embedding model and add one or more folders, or import images into the app-managed library.
2. The index job scans those folders, filters to supported image files, validates them, and extracts a creation date from EXIF or filesystem metadata.
3. The active vision-language model generates normalized embeddings for each image and stores them in the image FAISS vector store.
4. A face detector finds faces in each image, a face embedding model converts crops into embeddings, and the app assigns those faces to existing people clusters or creates new ones.
5. Person centroids and exemplar faces are updated, then duplicate people clusters are merged when similarity thresholds are met.
6. Vector stores and metadata are written to disk under `backend/data`, folder stats are updated, and thumbnails are generated on demand and cached.
7. Search requests embed the text query, rank images from the image vector store, and then apply folder, date, face-presence, person, and optional face-photo filters.
8. The API enriches results with thumbnails, dimensions, dates, favorites, collections, and people labels before returning them to the frontend.

## Data and storage

Glimpse keeps most runtime data locally:

- `glimpse.db`: SQLite database for core app records such as folders and collections
- `backend/data/image_vector_store`: image embeddings and image metadata
- `backend/data/face_vector_store`: face embeddings and face-level metadata
- `backend/data/person_vector_store`: people centroids and cluster metadata
- `backend/data/cache_dir`: downloaded model files
- `backend/data/thumbnails`: generated thumbnail cache
- `backend/data/library_state.json`: favorites and collection membership state
- `backend/data/model_state.json`: active model selection
- `saved_searches.json`: saved search definitions

## Project structure

### Top level

- `server.py`: FastAPI application entry point used by both direct backend runs and Electron
- `backend/`: backend API, indexing, search, models, state management, and tests
- `glimpse-front/`: React + Vite frontend
- `electron/`: desktop launcher that boots backend and frontend, then opens the app window
- `scripts/`: maintenance and inspection scripts for local data and clustering analysis
- `test_images/`: sample images for manual testing
- `requirements.txt`: root Python dependency entry that delegates to `backend/requirements.txt`
- `FEATURES.md`: broader product feature inventory

### Backend

- `backend/api/`: FastAPI route modules for indexing, search, folders, people, collections, images, and saved searches
- `backend/core/`: core search and indexing logic, including image embedding, face detection, face clustering, and vector store orchestration
- `backend/core/models/vision_language/`: model wrappers for CLIP and SigLIP-based image/text embedding
- `backend/core/models/faces/`: face detection, face embedding, and person-clustering store logic
- `backend/db_models/`: SQLModel table definitions and database setup
- `backend/schemas/`: request and response schemas used by the API layer
- `backend/services/`: application services for folders, imports, media metadata, thumbnails, collections, saved searches, and library state
- `backend/utils/`: lower-level helpers for image preparation, path normalization, and FAISS store utilities
- `backend/tests/`: backend test coverage
- `backend/data/`: generated runtime data such as vector stores, cached models, imported files, and thumbnails

### Frontend

- `glimpse-front/src/pages/`: main screens such as onboarding, search, people, collections, saved searches, index manager, and settings
- `glimpse-front/src/components/`: shared UI, layout, search widgets, and image viewer components
- `glimpse-front/src/contexts/`: app-wide state management for onboarding, models, indexing, and search results
- `glimpse-front/src/lib/`: API client and shared frontend utilities
- `glimpse-front/public/`: static assets served by Vite

### Desktop shell and scripts

- `electron/main.js`: starts Python, waits for backend health, starts Vite, then creates the Electron window
- `scripts/reset_library_data.py`: clears index, SQLite, and state files while preserving downloaded models
- `scripts/check_person_centroid_similarity.py`: helper for inspecting clustering behavior

## Development notes

- The app is designed around local file access and local inference.
- Search quality depends on indexing with the currently active model. Switching models is expected to trigger a rebuild so vector dimensions and checkpoints stay consistent.
- Model download is separate from model activation. The first download requires internet access because checkpoints are pulled through Hugging Face.

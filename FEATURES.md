# Feature Inventory

## Search

- **Natural language text search** — describe images and video scenes with free text via CLIP / SigLIP embeddings
- **Unified search** — queries both images and video keyframes in a single FAISS index, interleaves results by score
- **Image-to-image search** — upload an image or find similar from the image viewer
- **Face photo search** — upload a face photo to find all images containing that person
- **Video scene search** — text search over embedded video keyframes; results include exact scene timestamp and keyframe position

### Search filters

- Folder, date range (today / 7d / 30d / this year), face presence (any / faces / no faces)
- People filter (must include / prefer / exclude specific named people)
- Media type tabs (All / Images / Videos)

### Result features

- Paginated results (page size up to 200)
- Relevance score, duration, match timestamp, keyframe index
- Thumbnails with lazy loading, skeleton loading grids
- Empty state with example search suggestions

---

## Indexing

### Media support

| Type | Formats |
|---|---|
| **Images** | JPG, JPEG, PNG, WEBP, HEIC, TIFF, BMP, GIF |
| **Videos** | MP4, MOV, AVI, MKV, WEBM, M4V, MPG, MPEG |

### Embedding models

| Model | Dim | Quality |
|---|---|---|
| CLIP ViT-B/32 | 512 | Standard |
| SigLIP2 Base (patch16-224) | 768 | High |
| SigLIP2 Large (patch16-384) | 1024 | Best |

### Pipeline phases

1. **Scanning** — discover supported files, filter by type
2. **Image embeddings** — batch embed via active vision-language model
3. **Video keyframes** — scene detection (PySceneDetect), midpoint frame extraction (PyAV), embed with same model, store precise timestamp
4. **Faces** — YOLOv11n face detection, ViT-S face embedding, CosFace
5. **Clustering** — DBSCAN reclustering of faces into person identities
6. **Writing** — persist unified image+video FAISS store, face store, person centroids

### Index features

- Incremental (skips already-indexed files)
- Cancelable mid-batch with partial save
- Folder-level reindex, configurable batch size
- Face detection toggle, subfolder recursion toggle
- Progress polling every 1.2s with phase display

### Vector stores

- **Unified FAISS store** — images and video keyframes in one index, model-scoped namespaces
- **Face FAISS store** — per-face embeddings with source image path, box, confidence, quality
- **Person centroids** — weighted running-sum embeddings, merge support, top-exemplar selection

---

## Organization

- **Favorites** — toggle from results grid or image viewer, dedicated Favorites page
- **Collections** — named groupings with descriptions, add via file picker with auto-indexing, rename / delete
- **Saved searches** — save query + filter combinations, run / rename / delete
- **People / Faces** — auto-detected and clustered, rename, merge duplicates, face thumbnails, delete

---

## Video features

- Scene detection via PySceneDetect `ContentDetector`
- Keyframe extraction at scene midpoint via PyAV
- Keyframes embedded with same model used for images
- Precise scene midpoint timestamp stored per keyframe
- Results deduplicated per video (best-scoring keyframe kept)
- In-browser `<video>` player with native controls
- Lazily generated video thumbnails (mid-point frame), cached on disk

---

## Frontend

- **Pages**: Search, People, Person Detail, Favorites, Collections, Collection Detail, Saved Searches, Index Manager, Settings
- **Onboarding wizard**: 3-step flow — choose & download model, add folders / import photos, build index
- **Image viewer**: Full-screen modal, keyboard nav (arrows, Escape, F for favorite), metadata sidebar, "Find similar", "Open externally", "Copy path"
- **Sidebar**: Collapsible with count badges, active model, index freshness indicator, indexing progress
- **Theme**: Light / Dark / System via shadcn/ui
- **Keyboard shortcuts**: `/` to focus search, arrow keys in viewer, `F` to favorite
- **Empty states**: every page with actionable suggestions
- **Responsive grid**, toast notifications, skeleton loading, working overlays

---

## Backend

- **FAISS** in-memory vector stores with disk persistence
- **EXIF extraction** (DateTimeOriginal, DateTimeDigitized, CreatedDate)
- **Thumbnail caching** — SHA1-based keys (content + mtime), JPEG quality 85
- **SQLite** — folder records, collection metadata, saved searches via SQLModel
- **CUDA support** — automatic GPU detection with CPU fallback
- **Hugging Face Hub** model download with progress, token support via `.env`
- **Cross-platform file opening** — `os.startfile` (Win), `open` (macOS), `xdg-open` (Linux)
- **Cancellation pattern** — threading.Event, partial save on cancel
- **CORS middleware** for frontend dev on separate port
- **Structured logging** for indexing, API, face pipeline

---

## Settings

| Tab | Settings |
|---|---|
| General | Remember last page, confirm destructive actions, double-click behavior |
| Models | Download / activate / delete models, switch triggers reindex |
| Storage | Index size display, thumbnail cache size + clear |
| Indexing | Subfolder recursion, skip hidden folders, face detection toggle |
| Interface | Theme (System / Light / Dark), compact sidebar, thumbnail density |

---

## Desktop (Electron)

- Bundles FastAPI backend + Vite frontend into a single desktop app
- Boots backend, waits for `http://127.0.0.1:8000`, starts frontend on `http://localhost:8080`
- Opens native desktop window

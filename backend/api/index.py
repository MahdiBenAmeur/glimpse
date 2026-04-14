from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.config import FACE_VS_PATH, IMAGE_VS_PATH, PERSON_VS_PATH
from backend.core.indexing.index import index_batch
from backend.core.models.faces.store import reset_face_vector_stores, save_face_vector_stores
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.clip import ClipEmbeddingModel
from backend.core.models.vision_language.qwen import QwenEmbeddingModel
from backend.core.models.vision_language.siglip import SiglipEmbeddingModel
from backend.core.models.vision_language.store import reset_image_vector_store, save_image_vector_store
from backend.db_models.database import get_session
from backend.db_models.folder import Folder
from backend.services.folder_service import _folder_score
from backend.services.media_service import THUMBNAIL_CACHE_DIR, clear_thumbnail_cache
from backend.utils.image_processing import list_image_files
from backend.utils.path_utils import canonicalize_path, canonicalize_path_key
from backend.utils.vector_store_utils import delete_vs

router = APIRouter(prefix="/index", tags=["index"])

IndexPhase = Literal["idle", "scanning", "embeddings", "faces", "thumbnails", "writing", "complete"]
MODEL_STATE_PATH = Path("backend/data/model_state.json")


class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    quality: Literal["standard", "high", "best"]
    speed: Literal["fast", "moderate", "slow"]
    diskSize: str
    suitability: str
    status: Literal["not_installed", "installed", "active"]


class IndexingStatusResponse(BaseModel):
    phase: IndexPhase
    progress: int
    total: int
    processed: int
    facesDetected: int
    skipped: int
    currentFile: str | None = None
    error: str | None = None


class IndexSummaryResponse(BaseModel):
    activeModel: ModelInfo | None
    models: list[ModelInfo]
    indexingStatus: IndexingStatusResponse
    lastIndexedTime: str | None = None
    totalIndexedImages: int = 0
    totalPeople: int = 0
    totalFolders: int = 0
    indexedPaths: list[str] = Field(default_factory=list)


class StartIndexRequest(BaseModel):
    folderPaths: list[str] = Field(default_factory=list)
    folderIds: list[int] = Field(default_factory=list)
    modelId: str | None = None
    recursive: bool = True
    batchSize: int = Field(default=32, ge=1, le=512)
    resetIndex: bool = True


class ActivateModelRequest(BaseModel):
    modelId: str


class DownloadModelRequest(BaseModel):
    modelId: str


class StorageSummaryResponse(BaseModel):
    indexPath: str
    indexSizeBytes: int
    thumbnailCachePath: str
    thumbnailCacheBytes: int


MODEL_CATALOG: list[dict[str, Any]] = [
    {
        "id": "clip-vit-b32",
        "name": "CLIP ViT-B/32",
        "description": "Good balance of speed and quality",
        "quality": "standard",
        "speed": "fast",
        "diskSize": "600 MB",
        "suitability": "CPU & GPU",
        "factory": ClipEmbeddingModel,
    },
    {
        "id": "siglip2-base-patch16-224",
        "name": "SigLIP2",
        "description": "Higher quality semantic matching with slower indexing.",
        "quality": "high",
        "speed": "moderate",
        "diskSize": "1.5 GB",
        "suitability": "GPU recommended",
        "factory": SiglipEmbeddingModel,
    },
    {
        "id": "qwen-vl-embedding-2b",
        "name": "Qwen VL Embedding 2B",
        "description": "Best semantic understanding, but heavier to run locally.",
        "quality": "best",
        "speed": "slow",
        "diskSize": "5+ GB",
        "suitability": "High-memory GPU recommended",
        "factory": QwenEmbeddingModel,
    },
]

_model_map = {entry["id"]: entry for entry in MODEL_CATALOG}
_embedding_model_cache: dict[str, BaseEmbeddingModel] = {}
_download_state_cache: dict[str, bool] = {}
_indexing_thread: threading.Thread | None = None
_state_lock = threading.Lock()
_index_state: dict[str, Any] = {
    "phase": "idle",
    "progress": 0,
    "total": 0,
    "processed": 0,
    "facesDetected": 0,
    "skipped": 0,
    "currentFile": None,
    "error": None,
    "lastIndexedTime": None,
    "totalIndexedImages": 0,
    "indexedPaths": [],
}


def _load_active_model_id() -> str | None:
    if not MODEL_STATE_PATH.exists():
        return None
    try:
        with MODEL_STATE_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    active_model_id = payload.get("active_model_id")
    return active_model_id if isinstance(active_model_id, str) and active_model_id in _model_map else None


def _save_active_model_id(active_model_id: str | None) -> None:
    MODEL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MODEL_STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump({"active_model_id": active_model_id}, handle, indent=2)


_active_model_id = _load_active_model_id()


def get_model_catalog() -> list[dict[str, Any]]:
    return MODEL_CATALOG


def get_active_model_id() -> str | None:
    return _active_model_id


def get_embedding_model(model_id: str | None = None) -> BaseEmbeddingModel:
    resolved_model_id = model_id or _active_model_id
    model_entry = _model_map.get(resolved_model_id)
    if model_entry is None:
        raise ValueError(f"Unsupported model_id: {resolved_model_id}")
    cached = _embedding_model_cache.get(resolved_model_id)
    if cached is not None:
        return cached
    factory = model_entry["factory"]
    instance = factory()
    _embedding_model_cache[resolved_model_id] = instance
    return instance


def _is_model_downloaded(model_id: str) -> bool:
    cached = _download_state_cache.get(model_id)
    if cached is not None:
        return cached

    model_entry = _model_map.get(model_id)
    if model_entry is None:
        return False

    downloaded = model_entry["factory"]().is_model_downloaded()
    _download_state_cache[model_id] = downloaded
    return downloaded


def _set_model_downloaded(model_id: str, downloaded: bool) -> None:
    _download_state_cache[model_id] = downloaded


def _warm_active_model(model_id: str) -> None:
    for cached_model_id, model in list(_embedding_model_cache.items()):
        if cached_model_id != model_id:
            model.unload_model()
            del _embedding_model_cache[cached_model_id]

    model = get_embedding_model(model_id)
    model.load_model()


def get_active_model_info() -> dict[str, Any] | None:
    _ensure_active_model_is_available()
    model_entry = _model_map.get(_active_model_id)
    if model_entry is None:
        return None
    return _model_to_response(model_entry, active=True)


def _model_to_response(model_entry: dict[str, Any], *, active: bool) -> dict[str, Any]:
    is_downloaded = _is_model_downloaded(model_entry["id"])
    return {
        "id": model_entry["id"],
        "name": model_entry["name"],
        "description": model_entry["description"],
        "quality": model_entry["quality"],
        "speed": model_entry["speed"],
        "diskSize": model_entry["diskSize"],
        "suitability": model_entry["suitability"],
        "status": "active" if active and is_downloaded else ("installed" if is_downloaded else "not_installed"),
    }


def _ensure_active_model_is_available() -> None:
    global _active_model_id

    if _active_model_id is None:
        return

    model_entry = _model_map.get(_active_model_id)
    if model_entry is None:
        _active_model_id = None
        _save_active_model_id(None)
        return

    if not _is_model_downloaded(_active_model_id):
        _active_model_id = None
        _save_active_model_id(None)


def _load_meta_data(vs_path: str) -> dict[str, Any]:
    meta_path = Path(vs_path) / "meta_data.json"
    if not meta_path.exists():
        return {}
    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _count_store_records(vs_path: str) -> int:
    meta_data = _load_meta_data(vs_path)
    return sum(1 for key in meta_data if not str(key).startswith("_"))


def _copy_state() -> dict[str, Any]:
    with _state_lock:
        return dict(_index_state)


def _set_state(**kwargs: Any) -> None:
    with _state_lock:
        _index_state.update(kwargs)


def _reset_vector_stores() -> None:
    reset_image_vector_store()
    reset_face_vector_stores()
    delete_vs(IMAGE_VS_PATH)
    delete_vs(FACE_VS_PATH)
    delete_vs(PERSON_VS_PATH)


def _directory_size_bytes(path: str | Path) -> int:
    target = Path(path)
    if not target.exists():
        return 0
    if target.is_file():
        return int(target.stat().st_size)
    total = 0
    for file_path in target.rglob("*"):
        if file_path.is_file():
            total += int(file_path.stat().st_size)
    return total


def _coarse_phase(processed: int, total: int) -> IndexPhase:
    if total <= 0:
        return "scanning"
    ratio = processed / total
    if ratio < 0.10:
        return "scanning"
    if ratio < 0.60:
        return "embeddings"
    if ratio < 0.90:
        return "faces"
    return "writing"


def _upsert_folder_records(folder_paths: list[Path], *, session: Session) -> dict[str, Folder]:
    existing_by_key: dict[str, Folder] = {}
    for folder in session.exec(select(Folder)).all():
        key = canonicalize_path_key(folder.path)
        existing = existing_by_key.get(key)
        folder.path = canonicalize_path(folder.path)
        if existing is None or _folder_score(folder) > _folder_score(existing):
            existing_by_key[key] = folder
    existing: dict[str, Folder] = {}

    for folder_path in folder_paths:
        key = canonicalize_path_key(folder_path)
        if key in existing:
            continue
        matched = existing_by_key.get(key)
        if matched is None:
            folder = Folder(path=canonicalize_path(folder_path), image_count=0, status="ready", include_subfolders=True)
            session.add(folder)
            session.flush()
            matched = folder
        else:
            matched.path = canonicalize_path(matched.path)
        existing[key] = matched

    session.commit()
    return existing


def _run_index_job(folder_paths: list[Path], *, model_id: str, batch_size: int, recursive: bool, reset_index: bool) -> None:
    global _indexing_thread

    try:
        if reset_index:
            _reset_vector_stores()

        image_model = get_embedding_model(model_id)
        discovered_batches: list[tuple[Path, list[Path]]] = []
        total_files = 0

        for folder_path in folder_paths:
            files = list_image_files(folder_path, recursive=recursive)
            discovered_batches.append((folder_path, files))
            total_files += len(files)

        _set_state(
            phase="scanning",
            progress=0,
            total=total_files,
            processed=0,
            facesDetected=0,
            skipped=0,
            currentFile=str(folder_paths[0]) if folder_paths else None,
            error=None,
            indexedPaths=[canonicalize_path(path) for path in folder_paths],
        )

        folder_counts = {canonicalize_path_key(folder_path): len(files) for folder_path, files in discovered_batches}

        from backend.db_models.database import Session as DBSession, engine

        with DBSession(engine) as session:
            folder_records = _upsert_folder_records(folder_paths, session=session)
            for folder_path in folder_paths:
                folder_record = folder_records[canonicalize_path_key(folder_path)]
                folder_record.status = "scanning"
                session.add(folder_record)
            session.commit()

            processed_count = 0
            faces_detected = 0
            skipped_count = 0

            for folder_path, files in discovered_batches:
                if not files:
                    folder_record = folder_records[canonicalize_path_key(folder_path)]
                    folder_record.image_count = 0
                    folder_record.last_scan_time = datetime.utcnow()
                    folder_record.status = "ready"
                    session.add(folder_record)
                    session.commit()
                    continue

                for batch_start in range(0, len(files), batch_size):
                    batch_paths = files[batch_start : batch_start + batch_size]
                    current_file = str(batch_paths[0]) if batch_paths else str(folder_path)
                    batch_stats = index_batch(
                        batch_paths,
                        image_model,
                        batch_size=batch_size,
                        save_after_batch=False,
                    )
                    processed_count += int(batch_stats.get("processed_count", 0))
                    skipped_count += int(batch_stats.get("failed_count", 0))
                    faces_detected += int(batch_stats.get("face_indexing", {}).get("detected_face_count", 0))
                    progress = int(round((processed_count / total_files) * 100)) if total_files else 100

                    _set_state(
                        phase=_coarse_phase(processed_count, total_files),
                        progress=progress,
                        total=total_files,
                        processed=processed_count,
                        facesDetected=faces_detected,
                        skipped=skipped_count,
                        currentFile=current_file,
                    )

                folder_record = folder_records[canonicalize_path_key(folder_path)]
                folder_record.image_count = folder_counts[canonicalize_path_key(folder_path)]
                folder_record.last_scan_time = datetime.utcnow()
                folder_record.status = "ready"
                session.add(folder_record)
                session.commit()

        save_image_vector_store()
        save_face_vector_stores()

        completed_at = datetime.utcnow().isoformat()
        _set_state(
            phase="complete",
            progress=100,
            total=total_files,
            processed=total_files,
            facesDetected=faces_detected,
            skipped=skipped_count,
            currentFile=None,
            error=None,
            lastIndexedTime=completed_at,
            totalIndexedImages=_count_store_records(IMAGE_VS_PATH),
        )
    except Exception as exc:
        _set_state(
            phase="idle",
            currentFile=None,
            error=str(exc),
        )
    finally:
        _indexing_thread = None


def _resolve_folder_paths(payload: StartIndexRequest, session: Session) -> list[Path]:
    folder_paths = [Path(canonicalize_path(path)) for path in payload.folderPaths]

    if payload.folderIds:
        folders = session.exec(select(Folder).where(Folder.id.in_(payload.folderIds))).all()
        folder_paths.extend(Path(canonicalize_path(folder.path)) for folder in folders)

    if not folder_paths:
        folders = session.exec(select(Folder)).all()
        folder_paths.extend(Path(canonicalize_path(folder.path)) for folder in folders)

    unique_paths: list[Path] = []
    seen: set[str] = set()
    for path in folder_paths:
        key = canonicalize_path_key(path)
        if key not in seen:
            seen.add(key)
            unique_paths.append(Path(canonicalize_path(path)))
    return unique_paths


def _dedupe_folders_for_summary(folders: list[Folder]) -> list[Folder]:
    best_by_key: dict[str, Folder] = {}
    for folder in folders:
        key = canonicalize_path_key(folder.path)
        existing = best_by_key.get(key)
        folder.path = canonicalize_path(folder.path)
        if existing is None or _folder_score(folder) > _folder_score(existing):
            best_by_key[key] = folder
    return list(best_by_key.values())


@router.get("/models", response_model=list[ModelInfo])
def read_models() -> list[dict[str, Any]]:
    _ensure_active_model_is_available()
    return [_model_to_response(model_entry, active=model_entry["id"] == _active_model_id) for model_entry in MODEL_CATALOG]


@router.post("/models/activate", response_model=ModelInfo)
def activate_model(payload: ActivateModelRequest) -> dict[str, Any]:
    global _active_model_id

    model_entry = _model_map.get(payload.modelId)
    if model_entry is None:
        raise HTTPException(status_code=404, detail="Model not found")

    if not _is_model_downloaded(payload.modelId):
        raise HTTPException(status_code=409, detail="Model is not downloaded")

    _active_model_id = payload.modelId
    _save_active_model_id(_active_model_id)
    _warm_active_model(payload.modelId)
    return _model_to_response(model_entry, active=True)


@router.post("/models/download", response_model=ModelInfo)
def download_model(payload: DownloadModelRequest) -> dict[str, Any]:
    model_entry = _model_map.get(payload.modelId)
    if model_entry is None:
        raise HTTPException(status_code=404, detail="Model not found")

    model = get_embedding_model(payload.modelId)
    try:
        model.download_model()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Model download failed: {exc}") from exc

    _set_model_downloaded(payload.modelId, True)
    return _model_to_response(model_entry, active=model_entry["id"] == _active_model_id)


@router.get("/status", response_model=IndexingStatusResponse)
def read_index_status() -> dict[str, Any]:
    state = _copy_state()
    return {
        "phase": state["phase"],
        "progress": state["progress"],
        "total": state["total"],
        "processed": state["processed"],
        "facesDetected": state["facesDetected"],
        "skipped": state["skipped"],
        "currentFile": state["currentFile"],
        "error": state["error"],
    }


@router.get("/summary", response_model=IndexSummaryResponse)
def read_index_summary(session: Session = Depends(get_session)) -> dict[str, Any]:
    _ensure_active_model_is_available()
    state = _copy_state()
    folders = _dedupe_folders_for_summary(session.exec(select(Folder)).all())
    last_indexed_time = state["lastIndexedTime"]
    if last_indexed_time is None:
        scan_times = [folder.last_scan_time.isoformat() for folder in folders if folder.last_scan_time is not None]
        last_indexed_time = max(scan_times) if scan_times else None
    return {
        "activeModel": get_active_model_info(),
        "models": [_model_to_response(model_entry, active=model_entry["id"] == _active_model_id) for model_entry in MODEL_CATALOG],
        "indexingStatus": {
            "phase": state["phase"],
            "progress": state["progress"],
            "total": state["total"],
            "processed": state["processed"],
            "facesDetected": state["facesDetected"],
            "skipped": state["skipped"],
            "currentFile": state["currentFile"],
            "error": state["error"],
        },
        "lastIndexedTime": last_indexed_time,
        "totalIndexedImages": _count_store_records(IMAGE_VS_PATH),
        "totalPeople": _count_store_records(PERSON_VS_PATH),
        "totalFolders": len(folders),
        "indexedPaths": [folder.path for folder in folders],
    }


@router.post("/start", response_model=IndexSummaryResponse)
def start_indexing(payload: StartIndexRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    global _indexing_thread
    global _active_model_id

    if _indexing_thread is not None and _indexing_thread.is_alive():
        raise HTTPException(status_code=409, detail="Indexing is already running")

    folder_paths = _resolve_folder_paths(payload, session)
    if not folder_paths:
        raise HTTPException(status_code=400, detail="No folders available to index")

    missing_paths = [str(path) for path in folder_paths if not path.exists()]
    if missing_paths:
        raise HTTPException(status_code=400, detail={"message": "Some folders do not exist", "paths": missing_paths})

    if payload.modelId is not None:
        if payload.modelId not in _model_map:
            raise HTTPException(status_code=404, detail="Model not found")
        if not _is_model_downloaded(payload.modelId):
            raise HTTPException(status_code=409, detail="Model is not downloaded")
        _active_model_id = payload.modelId
        _save_active_model_id(_active_model_id)
        _warm_active_model(payload.modelId)
    elif _active_model_id is None:
        raise HTTPException(status_code=400, detail="Select a model before indexing")

    _set_state(
        phase="scanning",
        progress=0,
        total=0,
        processed=0,
        facesDetected=0,
        skipped=0,
        currentFile=str(folder_paths[0]),
        error=None,
        indexedPaths=[canonicalize_path(path) for path in folder_paths],
    )

    _indexing_thread = threading.Thread(
        target=_run_index_job,
        kwargs={
            "folder_paths": folder_paths,
            "model_id": _active_model_id,
            "batch_size": payload.batchSize,
            "recursive": payload.recursive,
            "reset_index": payload.resetIndex,
        },
        daemon=True,
    )
    _indexing_thread.start()
    return read_index_summary(session=session)


@router.post("/reindex", response_model=IndexSummaryResponse)
def reindex(payload: StartIndexRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    payload.resetIndex = True
    return start_indexing(payload=payload, session=session)


@router.get("/storage-summary", response_model=StorageSummaryResponse)
def read_storage_summary() -> dict[str, Any]:
    return {
        "indexPath": str(Path("backend/data").resolve()),
        "indexSizeBytes": _directory_size_bytes(IMAGE_VS_PATH) + _directory_size_bytes(FACE_VS_PATH) + _directory_size_bytes(PERSON_VS_PATH),
        "thumbnailCachePath": str(THUMBNAIL_CACHE_DIR.resolve()),
        "thumbnailCacheBytes": _directory_size_bytes(THUMBNAIL_CACHE_DIR),
    }


@router.post("/clear-cache", response_model=StorageSummaryResponse)
def clear_cache() -> dict[str, Any]:
    clear_thumbnail_cache()
    return read_storage_summary()

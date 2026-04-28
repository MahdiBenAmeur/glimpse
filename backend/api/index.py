from __future__ import annotations

import json
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.config import DATA_DIR, FACE_VS_PATH, IMAGE_VS_PATH, MODEL_STATE_PATH, PERSON_VS_PATH, THUMBNAIL_CACHE_DIR, models_cache_dir
from backend.core.indexing.index import index_batch
from backend.core.models.faces.store import finalize_face_clusters, reset_face_vector_stores, save_face_vector_stores
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.clip import ClipEmbeddingModel
from backend.core.models.vision_language.siglip import SiglipEmbeddingModel, SiglipLargeEmbeddingModel
from backend.core.models.vision_language.store import reset_image_vector_store, save_image_vector_store
from backend.db_models.database import get_session
from backend.db_models.folder import Folder
from backend.services.folder_service import _folder_score
from backend.services.media_service import clear_thumbnail_cache
from backend.utils.image_processing import list_image_files
from backend.utils.path_utils import canonicalize_path, canonicalize_path_key
from backend.utils.vector_store_utils import delete_vs

router = APIRouter(prefix="/index", tags=["index"])

IndexPhase = Literal["idle", "scanning", "embeddings", "faces", "clustering", "thumbnails", "writing", "cancelling", "cancelled", "complete"]
DEFAULT_INDEX_BATCH_SIZE = 32
SIGLIP2_LARGE_MODEL_ID = "siglip2-large-patch16-384"
SIGLIP2_LARGE_BATCH_SIZE = 8


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
    batchSize: int | None = Field(default=None, ge=1, le=512)
    resetIndex: bool = True


class ActivateModelRequest(BaseModel):
    modelId: str


class DownloadModelRequest(BaseModel):
    modelId: str


class ModelDownloadStatusResponse(BaseModel):
    modelId: str
    status: Literal["idle", "downloading", "complete", "error"]
    progress: int
    downloadedBytes: int
    totalBytes: int
    error: str | None = None


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
        "id": SIGLIP2_LARGE_MODEL_ID,
        "name": "SigLIP2 Large",
        "description": "Larger SigLIP2 checkpoint for stronger semantic matching.",
        "quality": "best",
        "speed": "slow",
        "diskSize": "3.3 GB",
        "suitability": "GPU recommended",
        "factory": SiglipLargeEmbeddingModel,
    },
]

_model_map = {entry["id"]: entry for entry in MODEL_CATALOG}
_embedding_model_cache: dict[str, BaseEmbeddingModel] = {}
_download_state_cache: dict[str, bool] = {}
_download_progress_cache: dict[str, dict[str, Any]] = {}
_indexing_thread: threading.Thread | None = None
_indexing_starting = False
_cancel_index_event = threading.Event()
_state_lock = threading.Lock()
_download_lock = threading.Lock()
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


def _log_index_api(message: str, **fields: Any) -> None:
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    suffix = ""
    if fields:
        suffix = " | " + ", ".join(f"{key}={value!r}" for key, value in fields.items())
    print(f"[{timestamp}] [INDEX API] {message}{suffix}", flush=True)


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


def _default_batch_size_for_model(model_id: str | None) -> int:
    if model_id == SIGLIP2_LARGE_MODEL_ID:
        return SIGLIP2_LARGE_BATCH_SIZE
    return DEFAULT_INDEX_BATCH_SIZE


def get_embedding_model(model_id: str | None = None) -> BaseEmbeddingModel:
    resolved_model_id = model_id or _active_model_id
    model_entry = _model_map.get(resolved_model_id)
    if model_entry is None:
        raise ValueError(f"Unsupported model_id: {resolved_model_id}")
    cached = _embedding_model_cache.get(resolved_model_id)
    if cached is not None:
        _log_index_api("Reusing cached embedding model", model_id=resolved_model_id, model_type=type(cached).__name__)
        return cached
    factory = model_entry["factory"]
    instance = factory()
    _embedding_model_cache[resolved_model_id] = instance
    _log_index_api("Created embedding model instance", model_id=resolved_model_id, model_type=type(instance).__name__)
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


def _parse_size_bytes(size_text: str) -> int:
    parts = size_text.strip().split()
    if len(parts) != 2:
        return 0
    try:
        value = float(parts[0])
    except ValueError:
        return 0
    unit = parts[1].lower()
    multipliers = {
        "kb": 1024,
        "mb": 1024**2,
        "gb": 1024**3,
    }
    return int(value * multipliers.get(unit, 0))


def _model_repo_cache_dir(model: BaseEmbeddingModel) -> Path:
    cache_name = f"models--{model.CKPT.replace('/', '--')}"
    return Path(models_cache_dir) / cache_name


def _model_cache_size_bytes(model: BaseEmbeddingModel) -> int:
    repo_cache_dir = _model_repo_cache_dir(model)
    blobs_dir = repo_cache_dir / "blobs"
    target = blobs_dir if blobs_dir.exists() else repo_cache_dir
    if not target.exists():
        return 0
    total = 0
    for file_path in target.rglob("*"):
        if file_path.is_file():
            try:
                total += int(file_path.stat().st_size)
            except OSError:
                continue
    return total


def _progress_from_bytes(downloaded_bytes: int, total_bytes: int, *, complete: bool = False) -> int:
    if complete:
        return 100
    if total_bytes <= 0:
        return 0
    return max(0, min(99, int((downloaded_bytes / total_bytes) * 100)))


def _set_download_progress(model_id: str, **fields: Any) -> None:
    with _download_lock:
        current = {
            "modelId": model_id,
            "status": "idle",
            "progress": 0,
            "downloadedBytes": 0,
            "totalBytes": 0,
            "error": None,
        }
        current.update(_download_progress_cache.get(model_id, {}))
        current.update(fields)
        _download_progress_cache[model_id] = current


def _get_download_progress(model_id: str) -> dict[str, Any] | None:
    with _download_lock:
        status = _download_progress_cache.get(model_id)
        return dict(status) if status is not None else None


def _warm_active_model(model_id: str) -> None:
    _log_index_api("Warming active model", model_id=model_id, cached_model_ids=list(_embedding_model_cache.keys()))
    for cached_model_id, model in list(_embedding_model_cache.items()):
        if cached_model_id != model_id:
            _log_index_api("Unloading cached model", cached_model_id=cached_model_id, model_type=type(model).__name__)
            model.unload_model()
            del _embedding_model_cache[cached_model_id]

    model = get_embedding_model(model_id)
    model.load_model()
    _log_index_api("Active model warmed successfully", model_id=model_id, model_type=type(model).__name__)


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


def _is_cancel_requested() -> bool:
    return _cancel_index_event.is_set()


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


def _save_partial_index_state() -> None:
    save_image_vector_store()
    save_face_vector_stores()


def _finish_cancelled_index_job(
    *,
    total_files: int,
    processed_count: int,
    faces_detected: int,
    skipped_count: int,
    current_file: str | None,
    session: Session | None = None,
    folder_records: dict[str, Folder] | None = None,
) -> None:
    if session is not None and folder_records is not None:
        for folder_record in folder_records.values():
            if folder_record.status == "scanning":
                folder_record.status = "ready"
                session.add(folder_record)
        session.commit()

    _log_index_api(
        "Saving partial vector stores after cancellation",
        processed_count=processed_count,
        total_files=total_files,
        faces_detected=faces_detected,
    )
    _save_partial_index_state()
    progress = int(round((processed_count / total_files) * 100)) if total_files else 0
    _set_state(
        phase="cancelled",
        progress=progress,
        total=total_files,
        processed=processed_count,
        facesDetected=faces_detected,
        skipped=skipped_count,
        currentFile=current_file,
        error=None,
        totalIndexedImages=_count_store_records(IMAGE_VS_PATH),
    )


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

    total_files = 0
    processed_count = 0
    faces_detected = 0
    skipped_count = 0
    current_file: str | None = None

    try:
        _log_index_api(
            "Index job started",
            model_id=model_id,
            batch_size=batch_size,
            recursive=recursive,
            reset_index=reset_index,
            folder_count=len(folder_paths),
        )
        if reset_index:
            _log_index_api("Resetting vector stores before indexing")
            _reset_vector_stores()

        image_model = get_embedding_model(model_id)
        _log_index_api("Resolved image model for index job", model_id=model_id, model_type=type(image_model).__name__)
        discovered_batches: list[tuple[Path, list[Path]]] = []

        for folder_path in folder_paths:
            if _is_cancel_requested():
                _finish_cancelled_index_job(
                    total_files=total_files,
                    processed_count=processed_count,
                    faces_detected=faces_detected,
                    skipped_count=skipped_count,
                    current_file=current_file,
                )
                return

            current_file = str(folder_path)
            files = list_image_files(folder_path, recursive=recursive)
            discovered_batches.append((folder_path, files))
            total_files += len(files)
            _log_index_api("Discovered files for folder", folder_path=str(folder_path), file_count=len(files))

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

        if _is_cancel_requested():
            _finish_cancelled_index_job(
                total_files=total_files,
                processed_count=processed_count,
                faces_detected=faces_detected,
                skipped_count=skipped_count,
                current_file=current_file,
            )
            return

        folder_counts = {canonicalize_path_key(folder_path): len(files) for folder_path, files in discovered_batches}

        from backend.db_models.database import Session as DBSession, engine

        with DBSession(engine) as session:
            folder_records = _upsert_folder_records(folder_paths, session=session)
            _log_index_api("Folder records upserted", folder_record_count=len(folder_records))
            for folder_path in folder_paths:
                folder_record = folder_records[canonicalize_path_key(folder_path)]
                folder_record.status = "scanning"
                session.add(folder_record)
            session.commit()

            for folder_path, files in discovered_batches:
                if _is_cancel_requested():
                    _finish_cancelled_index_job(
                        total_files=total_files,
                        processed_count=processed_count,
                        faces_detected=faces_detected,
                        skipped_count=skipped_count,
                        current_file=current_file,
                        session=session,
                        folder_records=folder_records,
                    )
                    return

                _log_index_api("Starting folder indexing", folder_path=str(folder_path), file_count=len(files))
                if not files:
                    folder_record = folder_records[canonicalize_path_key(folder_path)]
                    folder_record.image_count = 0
                    folder_record.last_scan_time = datetime.utcnow()
                    folder_record.status = "ready"
                    session.add(folder_record)
                    session.commit()
                    continue

                for batch_start in range(0, len(files), batch_size):
                    if _is_cancel_requested():
                        _finish_cancelled_index_job(
                            total_files=total_files,
                            processed_count=processed_count,
                            faces_detected=faces_detected,
                            skipped_count=skipped_count,
                            current_file=current_file,
                            session=session,
                            folder_records=folder_records,
                        )
                        return

                    batch_paths = files[batch_start : batch_start + batch_size]
                    current_file = str(batch_paths[0]) if batch_paths else str(folder_path)
                    _log_index_api(
                        "Starting batch",
                        folder_path=str(folder_path),
                        batch_start=batch_start,
                        batch_size=len(batch_paths),
                        current_file=current_file,
                    )
                    batch_stats = index_batch(
                        batch_paths,
                        image_model,
                        batch_size=batch_size,
                        save_after_batch=False,
                        cancel_check=_is_cancel_requested,
                    )
                    processed_count += int(batch_stats.get("processed_count", 0))
                    skipped_count += int(batch_stats.get("failed_count", 0))
                    faces_detected += int(batch_stats.get("face_indexing", {}).get("detected_face_count", 0))
                    progress = int(round((processed_count / total_files) * 100)) if total_files else 100
                    _log_index_api(
                        "Finished batch",
                        folder_path=str(folder_path),
                        batch_start=batch_start,
                        progress=progress,
                        processed_count=processed_count,
                        skipped_count=skipped_count,
                        faces_detected=faces_detected,
                        image_indexed_count=batch_stats.get("image_indexing", {}).get("indexed_count"),
                        face_indexed_count=batch_stats.get("face_indexing", {}).get("indexed_face_count"),
                    )

                    _set_state(
                        phase=_coarse_phase(processed_count, total_files),
                        progress=progress,
                        total=total_files,
                        processed=processed_count,
                        facesDetected=faces_detected,
                        skipped=skipped_count,
                        currentFile=current_file,
                    )

                    if _is_cancel_requested() or batch_stats.get("cancelled"):
                        _finish_cancelled_index_job(
                            total_files=total_files,
                            processed_count=processed_count,
                            faces_detected=faces_detected,
                            skipped_count=skipped_count,
                            current_file=current_file,
                            session=session,
                            folder_records=folder_records,
                        )
                        return

                folder_record = folder_records[canonicalize_path_key(folder_path)]
                folder_record.image_count = folder_counts[canonicalize_path_key(folder_path)]
                folder_record.last_scan_time = datetime.utcnow()
                folder_record.status = "ready"
                session.add(folder_record)
                session.commit()
                _log_index_api("Folder indexing finished", folder_path=str(folder_path), image_count=folder_record.image_count)

        if _is_cancel_requested():
            _finish_cancelled_index_job(
                total_files=total_files,
                processed_count=processed_count,
                faces_detected=faces_detected,
                skipped_count=skipped_count,
                current_file=current_file,
            )
            return

        _set_state(
            phase="clustering",
            progress=99,
            total=total_files,
            processed=processed_count,
            facesDetected=faces_detected,
            skipped=skipped_count,
            currentFile=None,
        )
        _log_index_api("Finalizing face clusters")
        final_face_merge_stats = finalize_face_clusters(cancel_check=_is_cancel_requested)
        if _is_cancel_requested() or final_face_merge_stats.get("cancelled"):
            _finish_cancelled_index_job(
                total_files=total_files,
                processed_count=processed_count,
                faces_detected=faces_detected,
                skipped_count=skipped_count,
                current_file=current_file,
            )
            return

        _log_index_api("Saving vector stores to disk")
        _save_partial_index_state()

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
            mergedPeople=int(final_face_merge_stats.get("merged_person_count", 0)),
        )
        _log_index_api(
            "Index job completed",
            completed_at=completed_at,
            total_files=total_files,
            faces_detected=faces_detected,
            skipped_count=skipped_count,
            merged_people=final_face_merge_stats.get("merged_person_count", 0),
        )
    except Exception as exc:
        _log_index_api("Index job crashed", error=str(exc), traceback=traceback.format_exc())
        _set_state(
            phase="idle",
            currentFile=None,
            error=str(exc),
        )
    finally:
        _indexing_thread = None
        _log_index_api("Index job thread cleared")


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


@router.get("/models/download-status/{model_id}", response_model=ModelDownloadStatusResponse)
def read_model_download_status(model_id: str) -> dict[str, Any]:
    model_entry = _model_map.get(model_id)
    if model_entry is None:
        raise HTTPException(status_code=404, detail="Model not found")

    status = _get_download_progress(model_id)
    if status is None:
        if _is_model_downloaded(model_id):
            total_bytes = _parse_size_bytes(model_entry["diskSize"])
            return {
                "modelId": model_id,
                "status": "complete",
                "progress": 100,
                "downloadedBytes": total_bytes,
                "totalBytes": total_bytes,
                "error": None,
            }
        total_bytes = _parse_size_bytes(model_entry["diskSize"])
        return {
            "modelId": model_id,
            "status": "idle",
            "progress": 0,
            "downloadedBytes": 0,
            "totalBytes": total_bytes,
            "error": None,
        }

    if status["status"] == "downloading":
        model = get_embedding_model(model_id)
        downloaded_bytes = _model_cache_size_bytes(model)
        total_bytes = int(status.get("totalBytes") or _parse_size_bytes(model_entry["diskSize"]))
        progress = _progress_from_bytes(downloaded_bytes, total_bytes)
        _set_download_progress(
            model_id,
            downloadedBytes=downloaded_bytes,
            totalBytes=total_bytes,
            progress=progress,
        )
        status = _get_download_progress(model_id) or status

    return status


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
    total_bytes = _parse_size_bytes(model_entry["diskSize"])
    current_bytes = _model_cache_size_bytes(model)
    _set_download_progress(
        payload.modelId,
        status="downloading",
        progress=_progress_from_bytes(current_bytes, total_bytes),
        downloadedBytes=current_bytes,
        totalBytes=total_bytes,
        error=None,
    )
    try:
        model.download_model()
    except Exception as exc:
        _set_download_progress(
            payload.modelId,
            status="error",
            progress=_progress_from_bytes(_model_cache_size_bytes(model), total_bytes),
            downloadedBytes=_model_cache_size_bytes(model),
            totalBytes=total_bytes,
            error=str(exc),
        )
        raise HTTPException(status_code=500, detail=f"Model download failed: {exc}") from exc

    _set_model_downloaded(payload.modelId, True)
    downloaded_bytes = max(_model_cache_size_bytes(model), total_bytes)
    _set_download_progress(
        payload.modelId,
        status="complete",
        progress=100,
        downloadedBytes=downloaded_bytes,
        totalBytes=total_bytes,
        error=None,
    )
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


@router.post("/cancel", response_model=IndexingStatusResponse)
def cancel_indexing() -> dict[str, Any]:
    if _indexing_starting or (_indexing_thread is not None and _indexing_thread.is_alive()):
        _cancel_index_event.set()
        _set_state(phase="cancelling", currentFile=None, error=None)
        _log_index_api("Index cancellation requested")
    else:
        _cancel_index_event.clear()
        _set_state(phase="cancelled", currentFile=None, error=None)
        _log_index_api("Index cancellation requested with no active job")
    return read_index_status()


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
    global _indexing_starting
    global _active_model_id

    if _indexing_starting or (_indexing_thread is not None and _indexing_thread.is_alive()):
        raise HTTPException(status_code=409, detail="Indexing is already running")
    _cancel_index_event.clear()
    _indexing_starting = True

    try:
        _log_index_api(
            "Received start indexing request",
            requested_model_id=payload.modelId,
            requested_batch_size=payload.batchSize,
            recursive=payload.recursive,
            reset_index=payload.resetIndex,
            folder_path_count=len(payload.folderPaths),
            folder_id_count=len(payload.folderIds),
        )
        folder_paths = _resolve_folder_paths(payload, session)
        if not folder_paths:
            raise HTTPException(status_code=400, detail="No folders available to index")

        missing_paths = [str(path) for path in folder_paths if not path.exists()]
        if missing_paths:
            raise HTTPException(status_code=400, detail={"message": "Some folders do not exist", "paths": missing_paths})

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

        if _is_cancel_requested():
            _set_state(phase="cancelled", currentFile=None, error=None)
            _indexing_starting = False
            return read_index_summary(session=session)

        resolved_batch_size = payload.batchSize if payload.batchSize is not None else _default_batch_size_for_model(_active_model_id)
        _log_index_api(
            "Resolved indexing configuration",
            active_model_id=_active_model_id,
            resolved_batch_size=resolved_batch_size,
            folder_paths=[str(path) for path in folder_paths],
        )

        _indexing_thread = threading.Thread(
            target=_run_index_job,
            kwargs={
                "folder_paths": folder_paths,
                "model_id": _active_model_id,
                "batch_size": resolved_batch_size,
                "recursive": payload.recursive,
                "reset_index": payload.resetIndex,
            },
            daemon=True,
        )
        _indexing_starting = False
        _indexing_thread.start()
        _log_index_api("Background index thread started", thread_name=_indexing_thread.name)
        return read_index_summary(session=session)
    except Exception:
        _indexing_starting = False
        raise


@router.post("/reindex", response_model=IndexSummaryResponse)
def reindex(payload: StartIndexRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    payload.resetIndex = True
    return start_indexing(payload=payload, session=session)


@router.get("/storage-summary", response_model=StorageSummaryResponse)
def read_storage_summary() -> dict[str, Any]:
    return {
        "indexPath": str(DATA_DIR.resolve()),
        "indexSizeBytes": _directory_size_bytes(IMAGE_VS_PATH) + _directory_size_bytes(FACE_VS_PATH) + _directory_size_bytes(PERSON_VS_PATH),
        "thumbnailCachePath": str(THUMBNAIL_CACHE_DIR.resolve()),
        "thumbnailCacheBytes": _directory_size_bytes(THUMBNAIL_CACHE_DIR),
    }


@router.post("/clear-cache", response_model=StorageSummaryResponse)
def clear_cache() -> dict[str, Any]:
    clear_thumbnail_cache()
    return read_storage_summary()

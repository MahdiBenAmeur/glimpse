from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

import torch

from backend.core.indexing.index_faces import index_face_batch
from backend.core.indexing.index_images import index_image_batch
from backend.core.models.faces.detector import load_face_detector
from backend.core.models.faces.embedding import load_face_embedding_model
from backend.core.models.faces.store import finalize_face_clusters, save_face_vector_stores
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.store import save_image_vector_store
from backend.services.app_settings_service import load_app_settings
from backend.services.library_state_service import load_image_vs_meta_data, load_video_vs_meta_data
from backend.utils.image_processing import coerce_image_paths, list_image_files, prepare_images
from backend.utils.path_utils import canonicalize_path_key


def _log_indexing(message: str, **fields) -> None:
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    suffix = ""
    if fields:
        suffix = " | " + ", ".join(f"{key}={value!r}" for key, value in fields.items())
    print(f"[{timestamp}] [INDEXING] {message}{suffix}", flush=True)


def _gpu_memory_snapshot() -> dict[str, float | int | str]:
    """Return lightweight CUDA memory counters for progress logging."""
    if not torch.cuda.is_available():
        return {"cuda": "unavailable"}

    return {
        "allocated_mb": round(torch.cuda.memory_allocated() / (1024 * 1024), 2),
        "reserved_mb": round(torch.cuda.memory_reserved() / (1024 * 1024), 2),
        "max_allocated_mb": round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2),
        "max_reserved_mb": round(torch.cuda.max_memory_reserved() / (1024 * 1024), 2),
    }


def _dedupe_unindexed_paths(
    valid_paths: list[Path],
    path_2_created_at: dict[Path, str | None],
) -> tuple[list[Path], dict[Path, str | None], list[dict]]:
    """Remove images already present in metadata and report the skipped paths."""
    image_vs_meta_data = load_image_vs_meta_data()
    seen_keys = {
        canonicalize_path_key(entry.get("image_path"))
        for key, entry in image_vs_meta_data.items()
        if not str(key).startswith("_") and isinstance(entry, dict) and entry.get("image_path")
    }

    unique_paths: list[Path] = []
    unique_created_at: dict[Path, str | None] = {}
    skipped_existing: list[dict] = []

    for path in valid_paths:
        path_key = canonicalize_path_key(path)
        if path_key in seen_keys:
            skipped_existing.append({"path": str(path), "reason": "already_indexed"})
            continue
        seen_keys.add(path_key)
        unique_paths.append(path)
        unique_created_at[path] = path_2_created_at.get(path)

    return unique_paths, unique_created_at, skipped_existing


def _dedupe_unindexed_video_paths(
    valid_paths: list[Path],
    path_2_created_at: dict[Path, str | None],
    path_2_duration: dict[Path, float | None],
) -> tuple[list[Path], dict[Path, str | None], dict[Path, float | None], list[dict]]:
    """Remove videos already present in metadata and report the skipped paths."""
    video_vs_meta_data = load_video_vs_meta_data()
    seen_keys = {
        canonicalize_path_key(entry.get("video_path"))
        for key, entry in video_vs_meta_data.items()
        if not str(key).startswith("_") and isinstance(entry, dict) and entry.get("video_path")
    }

    unique_paths: list[Path] = []
    unique_created_at: dict[Path, str | None] = {}
    unique_duration: dict[Path, float | None] = {}
    skipped_existing: list[dict] = []

    for path in valid_paths:
        path_key = canonicalize_path_key(path)
        if path_key in seen_keys:
            skipped_existing.append({"path": str(path), "reason": "already_indexed"})
            continue
        seen_keys.add(path_key)
        unique_paths.append(path)
        unique_created_at[path] = path_2_created_at.get(path)
        unique_duration[path] = path_2_duration.get(path)

    return unique_paths, unique_created_at, unique_duration, skipped_existing


def _chunk_paths(paths: Sequence[Path], batch_size: int) -> list[list[Path]]:
    """Split paths into fixed-size batches for incremental indexing."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    return [list(paths[start : start + batch_size]) for start in range(0, len(paths), batch_size)]


def index_batch(
    image_paths: Sequence[str | Path],
    image_model: BaseEmbeddingModel,
    *,
    batch_size: int = 32,
    save_after_batch: bool = False,
    cancel_check: Callable[[], bool] | None = None,
) -> dict:
    """Run the full indexing workflow for one batch of images.

    The method prepares paths once, skips images already present in metadata,
    loads the image model and optional face models, writes image embeddings
    first, then runs the face pipeline. The optional cancel check is evaluated
    between expensive stages so background indexing can stop cleanly.
    """
    normalized_paths = coerce_image_paths(image_paths)
    _log_indexing("index_batch started", input_count=len(normalized_paths), batch_size=batch_size, save_after_batch=save_after_batch)
    valid_paths, failed_items, path_2_created_at = prepare_images(normalized_paths)
    _log_indexing(
        "Prepared images for batch",
        valid_count=len(valid_paths),
        failed_count=len(failed_items),
        first_valid=str(valid_paths[0]) if valid_paths else None,
    )

    stats = {
        "input_count": len(normalized_paths),
        "processed_count": len(valid_paths),
        "failed_count": len(failed_items),
        "failed_items": failed_items,
        "image_indexing": {},
        "face_indexing": {},
        "total_people_in_batch": 0,
        "new_people_count": 0,
    }

    if cancel_check is not None and cancel_check():
        stats["processed_count"] = 0
        stats["cancelled"] = True
        return stats

    if not valid_paths:
        _log_indexing("No valid paths after image preparation")
        return stats

    valid_paths, path_2_created_at, skipped_existing = _dedupe_unindexed_paths(valid_paths, path_2_created_at)
    stats["skipped_existing_count"] = len(skipped_existing)
    stats["skipped_existing_items"] = skipped_existing
    _log_indexing(
        "Deduped batch against existing index",
        remaining_count=len(valid_paths),
        skipped_existing_count=len(skipped_existing),
    )

    if not valid_paths:
        _log_indexing("All valid paths were already indexed")
        return stats

    if cancel_check is not None and cancel_check():
        stats["processed_count"] = 0
        stats["cancelled"] = True
        return stats

    _log_indexing("Loading models required for batch", model_type=type(image_model).__name__)
    image_model.load_model()
    face_detection_enabled = bool(load_app_settings().get("face_detection_enabled", True))
    if face_detection_enabled:
        load_face_detector()
        load_face_embedding_model()
    _log_indexing("All models loaded for batch", **_gpu_memory_snapshot())

    if cancel_check is not None and cancel_check():
        stats["processed_count"] = 0
        stats["cancelled"] = True
        return stats

    image_stats = index_image_batch(
        image_model,
        valid_paths,
        validate_inputs=False,
        path_2_created_at=path_2_created_at,
    )
    _log_indexing(
        "Image indexing finished for batch",
        indexed_count=image_stats.get("indexed_count"),
        failed_count=image_stats.get("failed_count"),
        store_total=image_stats.get("store_total"),
        **_gpu_memory_snapshot(),
    )

    if cancel_check is not None and cancel_check():
        stats["image_indexing"] = image_stats
        stats["cancelled"] = True
        return stats

    if face_detection_enabled:
        face_stats = index_face_batch(
            valid_paths,
            embedding_batch_size=batch_size,
            validate_inputs=False,
            path_2_created_at=path_2_created_at,
            cancel_check=cancel_check,
        )
        _log_indexing(
            "Face indexing finished for batch",
            detected_face_count=face_stats.get("detected_face_count"),
            indexed_face_count=face_stats.get("indexed_face_count"),
            assigned_person_count=face_stats.get("assigned_person_count"),
            **_gpu_memory_snapshot(),
        )
    else:
        face_stats = {
            "input_count": len(valid_paths),
            "valid_count": len(valid_paths),
            "failed_count": 0,
            "failed_items": [],
            "detected_face_count": 0,
            "detected_image_count": 0,
            "indexed_face_count": 0,
            "new_person_count": 0,
            "assigned_person_count": 0,
            "assigned_person_ids": [],
            "person_store_total": 0,
            "face_store_total": 0,
        }
        _log_indexing("Face indexing skipped because face detection is disabled")

    stats["image_indexing"] = image_stats
    stats["face_indexing"] = face_stats
    stats["total_people_in_batch"] = int(face_stats.get("assigned_person_count", 0))
    stats["new_people_count"] = int(face_stats.get("new_person_count", 0))
    stats["person_store_total"] = int(face_stats.get("person_store_total", 0))

    if save_after_batch:
        save_image_vector_store()
        save_face_vector_stores()
        _log_indexing("Saved vector stores after batch")

    _log_indexing(
        "index_batch completed",
        processed_count=stats["processed_count"],
        failed_count=stats["failed_count"],
        new_people_count=stats["new_people_count"],
        **_gpu_memory_snapshot(),
    )
    return stats


def index_folder(
    folder_path: str | Path,
    image_model: BaseEmbeddingModel,
    *,
    batch_size: int = 32,
    recursive: bool = True,
    save_after_batch: bool = False,
) -> dict:
    """Index every image discovered under a folder.

    Files are discovered first, split into batches, then passed through
    index_batch. Batch summaries are accumulated into folder-level progress
    stats, and face clusters are finalized once all batches have been processed.
    """
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {folder}")

    discovered_files = list_image_files(folder, recursive=recursive)
    batches = _chunk_paths(discovered_files, batch_size) if discovered_files else []

    stats = {
        "folder_path": str(folder),
        "recursive": recursive,
        "batch_size": batch_size,
        "discovered_file_count": len(discovered_files),
        "batch_count": len(batches),
        "processed_count": 0,
        "failed_count": 0,
        "failed_items": [],
        "image_indexed_count": 0,
        "face_indexed_count": 0,
        "total_people_in_batches": 0,
        "new_people_count": 0,
        "final_person_store_total": 0,
        "completion_count": 0,
        "completion_percent": 0.0,
        "batches": [],
    }

    for batch_index, batch_paths in enumerate(batches, start=1):
        batch_stats = index_batch(
            batch_paths,
            image_model,
            batch_size=batch_size,
            save_after_batch=save_after_batch,
        )

        stats["processed_count"] += int(batch_stats.get("processed_count", 0))
        stats["failed_count"] += int(batch_stats.get("failed_count", 0))
        stats["failed_items"].extend(batch_stats.get("failed_items", []))
        stats["image_indexed_count"] += int(batch_stats.get("image_indexing", {}).get("indexed_count", 0))
        stats["face_indexed_count"] += int(batch_stats.get("face_indexing", {}).get("indexed_face_count", 0))
        stats["total_people_in_batches"] += int(batch_stats.get("total_people_in_batch", 0))
        stats["new_people_count"] += int(batch_stats.get("new_people_count", 0))
        stats["final_person_store_total"] = int(batch_stats.get("person_store_total", stats["final_person_store_total"]))
        stats["completion_count"] += len(batch_paths)
        if stats["discovered_file_count"] > 0:
            stats["completion_percent"] = round(
                (stats["completion_count"] / stats["discovered_file_count"]) * 100,
                2,
            )
        stats["batches"].append(
            {
                "batch_index": batch_index,
                "batch_file_count": len(batch_paths),
                "completion_count": stats["completion_count"],
                "completion_percent": stats["completion_percent"],
                "stats": batch_stats,
            }
        )
        print("*"*40)
        print(f"Completed batch {batch_index}/{stats['batch_count']} - {stats['completion_percent']}% complete")
        print(f"Batch stats: {batch_stats}")

    finalize_face_clusters()
    save_image_vector_store()
    save_face_vector_stores()
    return stats

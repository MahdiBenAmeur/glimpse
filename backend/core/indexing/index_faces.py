from typing import Sequence
from typing import Callable
from datetime import datetime

import torch

from backend.core.models.faces.detector import detect_faces
from backend.core.models.faces.detector import crop_faces
from backend.core.models.faces.embedding import embed_faces
from backend.core.models.faces.embedding import load_face_embedding_model
from backend.core.models.faces.store import add_faces_to_vector_store
from backend.core.models.faces.store import load_face_vector_store
from backend.core.models.faces.store import load_person_vector_store
from backend.utils.image_processing import coerce_image_paths, prepare_images
from pathlib import Path


def _log_face_indexing(message: str, **fields) -> None:
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    suffix = ""
    if fields:
        suffix = " | " + ", ".join(f"{key}={value!r}" for key, value in fields.items())
    print(f"[{timestamp}] [FACE INDEXING] {message}{suffix}", flush=True)


def _gpu_memory_snapshot() -> dict[str, float | int | str]:
    if not torch.cuda.is_available():
        return {"cuda": "unavailable"}

    return {
        "allocated_mb": round(torch.cuda.memory_allocated() / (1024 * 1024), 2),
        "reserved_mb": round(torch.cuda.memory_reserved() / (1024 * 1024), 2),
        "max_allocated_mb": round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2),
        "max_reserved_mb": round(torch.cuda.max_memory_reserved() / (1024 * 1024), 2),
    }


def index_face_batch(
    image_paths: Sequence[str | Path],
    *,
    embedding_batch_size: int = 32,
    validate_inputs: bool = True,
    path_2_created_at: dict[Path, str | None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict:
    if validate_inputs:
        valid_paths, failed_items, prepared_created_at = prepare_images(image_paths)
        path_2_created_at = prepared_created_at
    else:
        valid_paths, failed_items = coerce_image_paths(image_paths), []
        path_2_created_at = path_2_created_at or {}

    stats = {
        "input_count": len(image_paths),
        "valid_count": len(valid_paths),
        "failed_count": len(failed_items),
        "failed_items": failed_items,
        "detected_face_count": 0,
        "detected_image_count": 0,
        "indexed_face_count": 0,
        "new_person_count": 0,
        "assigned_person_count": 0,
        "assigned_person_ids": [],
        "person_store_total": 0,
        "face_store_total": 0,
    }

    if not valid_paths:
        return stats

    if cancel_check is not None and cancel_check():
        stats["cancelled"] = True
        return stats

    _log_face_indexing("Starting face detection", input_count=len(valid_paths), **_gpu_memory_snapshot())
    path_2_boxes = detect_faces(valid_paths)
    _log_face_indexing(
        "Face detection finished",
        detected_image_count=len(path_2_boxes),
        detected_face_count=sum(len(boxes) for boxes in path_2_boxes.values()),
        **_gpu_memory_snapshot(),
    )
    stats["detected_image_count"] = len(path_2_boxes)
    stats["detected_face_count"] = sum(len(boxes) for boxes in path_2_boxes.values())

    if cancel_check is not None and cancel_check():
        stats["cancelled"] = True
        return stats

    if not path_2_boxes:
        face_vs, _ = load_face_vector_store()
        person_vs, _ = load_person_vector_store()
        stats["person_store_total"] = int(person_vs.ntotal)
        stats["face_store_total"] = int(face_vs.ntotal)
        return stats

    _log_face_indexing("Starting face crop extraction", **_gpu_memory_snapshot())
    path_2_crops = crop_faces(path_2_boxes)
    _log_face_indexing(
        "Face crop extraction finished",
        cropped_image_count=len(path_2_crops),
        cropped_face_count=sum(len(crops) for crops in path_2_crops.values()),
        **_gpu_memory_snapshot(),
    )
    if cancel_check is not None and cancel_check():
        stats["cancelled"] = True
        return stats

    _log_face_indexing("Starting face embedding", batch_size=embedding_batch_size, **_gpu_memory_snapshot())
    path_2_embeddings = embed_faces(path_2_crops, batch_size=embedding_batch_size)
    _log_face_indexing(
        "Face embedding finished",
        embedded_image_count=len(path_2_embeddings),
        embedded_face_count=sum(int(embeddings.shape[0]) for embeddings in path_2_embeddings.values()),
        **_gpu_memory_snapshot(),
    )
    if cancel_check is not None and cancel_check():
        stats["cancelled"] = True
        return stats

    _log_face_indexing("Writing face embeddings to store", **_gpu_memory_snapshot())
    store_stats = add_faces_to_vector_store(
        path_2_embeddings,
        path_2_boxes,
        path_2_created_at=path_2_created_at,
        cancel_check=cancel_check,
    )
    _log_face_indexing("Finished writing face embeddings to store", **_gpu_memory_snapshot())
    stats.update(store_stats)
    return stats

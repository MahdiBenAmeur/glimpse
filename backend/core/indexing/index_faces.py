from typing import Sequence

from backend.core.models.faces.detector import detect_faces
from backend.core.models.faces.detector import crop_faces
from backend.core.models.faces.embedding import embed_faces
from backend.core.models.faces.embedding import load_face_embedding_model
from backend.core.models.faces.store import add_faces_to_vector_store
from backend.core.models.faces.store import load_face_vector_store
from backend.core.models.faces.store import load_person_vector_store
from backend.utils.image_processing import coerce_image_paths, prepare_images
from pathlib import Path

def index_face_batch(
    image_paths: Sequence[str | Path],
    *,
    embedding_batch_size: int = 32,
    validate_inputs: bool = True,
    path_2_created_at: dict[Path, str | None] | None = None,
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

    path_2_boxes = detect_faces(valid_paths)
    stats["detected_image_count"] = len(path_2_boxes)
    stats["detected_face_count"] = sum(len(boxes) for boxes in path_2_boxes.values())

    if not path_2_boxes:
        face_vs, _ = load_face_vector_store()
        person_vs, _ = load_person_vector_store()
        stats["person_store_total"] = int(person_vs.ntotal)
        stats["face_store_total"] = int(face_vs.ntotal)
        return stats

    path_2_crops = crop_faces(path_2_boxes)
    path_2_embeddings = embed_faces(path_2_crops, batch_size=embedding_batch_size)
    store_stats = add_faces_to_vector_store(
        path_2_embeddings,
        path_2_boxes,
        path_2_created_at=path_2_created_at,
    )
    stats.update(store_stats)
    return stats

from pathlib import Path
from typing import Sequence

from backend.core.indexing.index_images import coerce_image_paths, prepare_image_paths
from backend.core.models.faces.detector import detect_faces
from backend.core.models.faces.detector import crop_faces
from backend.core.models.faces.embedding import embed_faces
from backend.core.models.faces.embedding import load_face_embedding_model
from backend.core.models.faces.store import add_faces_to_vector_store
from backend.core.models.faces.store import load_face_vector_store
from backend.core.models.faces.store import load_person_vector_store


def index_face_batch(
    image_paths: Sequence[str | Path],
    *,
    embedding_batch_size: int = 32,
    validate_inputs: bool = True,
) -> dict:
    valid_paths, failed_items = prepare_image_paths(image_paths) if validate_inputs else (coerce_image_paths(image_paths), [])

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
    store_stats = add_faces_to_vector_store(path_2_embeddings, path_2_boxes)
    stats.update(store_stats)
    return stats

from pathlib import Path
from typing import Sequence

from backend.core.indexing.index_faces import index_face_batch
from backend.core.indexing.index_images import coerce_image_paths
from backend.core.indexing.index_images import index_image_batch
from backend.core.indexing.index_images import prepare_image_paths
from backend.core.models.faces.detector import load_face_detector
from backend.core.models.faces.embedding import load_face_embedding_model
from backend.core.models.faces.store import save_face_vector_stores
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.store import save_image_vector_store


def index_batch(
    image_paths: Sequence[str | Path],
    image_model: BaseEmbeddingModel,
    *,
    face_embedding_batch_size: int = 32,
    save_after_batch: bool = False,
) -> dict:
    normalized_paths = coerce_image_paths(image_paths)
    valid_paths, failed_items = prepare_image_paths(normalized_paths)

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

    if not valid_paths:
        return stats

    image_model.load_model()
    load_face_detector()
    load_face_embedding_model()

    image_stats = index_image_batch(
        image_model,
        valid_paths,
        validate_inputs=False,
    )
    face_stats = index_face_batch(
        valid_paths,
        embedding_batch_size=face_embedding_batch_size,
        validate_inputs=False,
    )

    stats["image_indexing"] = image_stats
    stats["face_indexing"] = face_stats
    stats["total_people_in_batch"] = int(face_stats.get("assigned_person_count", 0))
    stats["new_people_count"] = int(face_stats.get("new_person_count", 0))
    stats["person_store_total"] = int(face_stats.get("person_store_total", 0))

    if save_after_batch:
        save_image_vector_store()
        save_face_vector_stores()

    return stats

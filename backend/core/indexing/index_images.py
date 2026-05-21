from typing import Sequence

import numpy as np

from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.store import load_image_vector_store
from backend.utils.image_processing import coerce_image_paths, prepare_images
from backend.utils.vector_store_utils import consume_next_id
from pathlib import Path

def index_image_batch(
    image_model: BaseEmbeddingModel,
    image_paths: Sequence[str | Path],
    *,
    validate_inputs: bool = True,
    path_2_created_at: dict[Path, str | None] | None = None,
) -> dict:
    """Embed valid images and append them to the image vector store.

    When validate_inputs is false the caller is expected to have already run
    image preparation, so this function can reuse created_at metadata without
    re-opening every file. New ids come from store metadata, then embeddings and
    image path records are written together.
    """
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
        "indexed_count": 0,
        "indexed_ids": [],
    }

    if not valid_paths:
        return stats

    embeddings = image_model.embed_images(valid_paths)
    image_vector_store, image_store_meta_data = load_image_vector_store(image_model)
    image_ids = [consume_next_id(image_store_meta_data) for _ in valid_paths]
    ids_array = np.array(image_ids, dtype=np.int64)
    embeddings_array = embeddings.numpy().astype("float32")

    image_vector_store.add_with_ids(embeddings_array, ids_array)

    for image_path, image_id in zip(valid_paths, image_ids):
        image_store_meta_data[str(image_id)] = {
            "image_path": str(image_path),
            "created_at": path_2_created_at.get(image_path) if path_2_created_at is not None else None,
        }
        stats["indexed_ids"].append(image_id)

    stats["indexed_count"] = len(image_ids)
    stats["store_total"] = int(image_vector_store.ntotal)
    return stats

from typing import Sequence

import numpy as np

from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.store import load_image_vector_store
from backend.core.models.vision_language.unified_store import (
    load_unified_vector_store,
    save_unified_vector_store,
)
from backend.utils.image_processing import coerce_image_paths, prepare_images
from backend.utils.vector_store_utils import consume_next_id
from pathlib import Path

_IS_UNIFIED = False
_UNIFIED_MODEL_ID: str | None = None


def _set_unified_context(model_id: str | None) -> None:
    global _IS_UNIFIED, _UNIFIED_MODEL_ID
    _IS_UNIFIED = model_id is not None
    _UNIFIED_MODEL_ID = model_id


def index_image_batch(
    image_model: BaseEmbeddingModel,
    image_paths: Sequence[str | Path],
    *,
    validate_inputs: bool = True,
    path_2_created_at: dict[Path, str | None] | None = None,
    model_id: str | None = None,
) -> dict:
    """Embed valid images and append them to the image or unified vector store.

    When ``model_id`` corresponds to a unified model (X-CLIP), images are stored
    in the unified store with ``media_type: "image"``. Otherwise the legacy image
    store is used.
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

    is_unified = model_id is not None and model_id == _UNIFIED_MODEL_ID
    if is_unified:
        assert model_id is not None
        vs, meta = load_unified_vector_store(model_id)
        file_key = "file_path"
    else:
        vs, meta = load_image_vector_store(image_model, model_id)
        file_key = "image_path"

    image_ids = [consume_next_id(meta) for _ in valid_paths]
    ids_array = np.array(image_ids, dtype=np.int64)
    embeddings_array = embeddings.numpy().astype("float32")

    vs.add_with_ids(embeddings_array, ids_array)

    for image_path, image_id in zip(valid_paths, image_ids):
        entry = {
            file_key: str(image_path),
            "created_at": path_2_created_at.get(image_path) if path_2_created_at is not None else None,
        }
        if is_unified:
            entry["media_type"] = "image"
            entry["file_id"] = image_id
        meta[str(image_id)] = entry
        stats["indexed_ids"].append(image_id)

    if is_unified:
        save_unified_vector_store()

    stats["indexed_count"] = len(image_ids)
    stats["store_total"] = int(vs.ntotal)
    return stats

import faiss
import numpy as np
from typing import Any, Callable

from backend.config import IMAGE_VS_PATH
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.utils.vector_store_utils import create_empty_index, delete_vs, load_or_init_vector_store, save_vs


image_vs = None
image_meta_data = None


def get_loaded_image_metadata() -> dict | None:
    """Return in-memory image metadata when the image store is loaded."""
    return image_meta_data


def reset_image_vector_store() -> None:
    """Clear the in-memory image vector store so it reloads from disk next time."""
    global image_vs
    global image_meta_data
    image_vs = None
    image_meta_data = None


def _ensure_image_store_metadata(meta_data: dict, image_model: BaseEmbeddingModel, emb_dim: int) -> None:
    """Validate or initialize model checkpoint and embedding dimension metadata."""
    model_ckpt = getattr(image_model, "CKPT", image_model.__class__.__name__)

    if "_embedding_dim" not in meta_data:
        meta_data["_embedding_dim"] = emb_dim
    elif int(meta_data["_embedding_dim"]) != emb_dim:
        raise ValueError(
            f"Image vector store dimension mismatch: store={meta_data['_embedding_dim']} current={emb_dim}"
        )

    if "_model_ckpt" not in meta_data:
        meta_data["_model_ckpt"] = model_ckpt
    elif meta_data["_model_ckpt"] != model_ckpt:
        raise ValueError(
            f"Image vector store model mismatch: store={meta_data['_model_ckpt']} current={model_ckpt}"
        )


def load_image_vector_store(emb_dim: int | None = None, image_model: BaseEmbeddingModel | None = None) -> tuple[faiss.Index, dict]:
    """Load the cached image vector store, creating it when no saved store exists."""
    global image_vs
    global image_meta_data

    if image_vs is not None and image_meta_data is not None:
        resolved_dim = int(emb_dim if emb_dim is not None else image_meta_data.get("_embedding_dim") or 512)
        if image_model is not None:
            _ensure_image_store_metadata(image_meta_data, image_model, resolved_dim)
        return image_vs, image_meta_data

    resolved_dim = int(emb_dim or 512)
    image_vs, image_meta_data = load_or_init_vector_store(IMAGE_VS_PATH, emb_dim=resolved_dim)
    resolved_dim = int(image_meta_data.get("_embedding_dim") or resolved_dim)
    if image_model is not None:
        _ensure_image_store_metadata(image_meta_data, image_model, resolved_dim)
    return image_vs, image_meta_data


def save_image_vector_store() -> None:
    """Persist the loaded image vector store and metadata to disk."""
    if image_vs is None or image_meta_data is None:
        return
    save_vs(image_vs, image_meta_data, IMAGE_VS_PATH)


def purge_image_entries(match_image_path: Callable[[str], bool]) -> dict[str, Any]:
    """Remove image vectors whose paths match a predicate and rebuild the index.

    Reserved metadata keys are preserved, matching image ids are dropped, and
    the FAISS index is reconstructed from the vectors that remain. If every
    image is removed, the persisted vector store is deleted instead of keeping
    an empty file pair around.
    """
    global image_vs
    global image_meta_data

    if image_vs is None or image_meta_data is None:
        if not IMAGE_VS_PATH.exists():
            return {"removed_ids": [], "removed_count": 0, "remaining_count": 0}
        image_vs, image_meta_data = load_or_init_vector_store(IMAGE_VS_PATH, emb_dim=512)

    removed_ids: list[int] = []
    kept_ids: list[int] = []
    next_meta_data = {
        str(key): value
        for key, value in image_meta_data.items()
        if str(key).startswith("_")
    }

    for key, value in image_meta_data.items():
        if str(key).startswith("_") or not isinstance(value, dict):
            continue
        image_path = value.get("image_path")
        if image_path and match_image_path(str(image_path)):
            removed_ids.append(int(key))
            continue
        kept_ids.append(int(key))
        next_meta_data[str(key)] = value

    if not removed_ids:
        return {"removed_ids": [], "removed_count": 0, "remaining_count": len(kept_ids)}

    if not kept_ids:
        reset_image_vector_store()
        delete_vs(IMAGE_VS_PATH)
        return {"removed_ids": removed_ids, "removed_count": len(removed_ids), "remaining_count": 0}

    emb_dim = int(image_meta_data.get("_embedding_dim") or 512)
    rebuilt_index = create_empty_index(emb_dim)
    rebuilt_vectors: list[np.ndarray] = []
    rebuilt_ids: list[int] = []
    for image_id in kept_ids:
        rebuilt_vectors.append(image_vs.reconstruct(int(image_id)))
        rebuilt_ids.append(int(image_id))

    if rebuilt_vectors:
        rebuilt_index.add_with_ids(
            np.asarray(rebuilt_vectors, dtype="float32"),
            np.asarray(rebuilt_ids, dtype=np.int64),
        )

    image_vs = rebuilt_index
    image_meta_data = next_meta_data
    save_image_vector_store()
    return {
        "removed_ids": removed_ids,
        "removed_count": len(removed_ids),
        "remaining_count": len(kept_ids),
    }

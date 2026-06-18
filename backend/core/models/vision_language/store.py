import faiss
import numpy as np
from pathlib import Path
from typing import Any
import json

from backend.config import IMAGE_META_PATH, IMAGE_VS_PATH, model_scoped_vs_path
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.utils.path_utils import canonicalize_path, canonicalize_path_key
from backend.utils.vector_store_utils import create_empty_index, delete_vs, load_or_init_vector_store, save_vs


image_vs = None
image_vs_meta_data = None


def get_loaded_image_vs_metadata() -> dict | None:
    """Return in-memory image metadata when the image store is loaded."""
    return image_vs_meta_data


def reset_image_vector_store() -> None:
    """Clear the in-memory image vector store so it reloads from disk next time."""
    global image_vs
    global image_vs_meta_data
    image_vs = None
    image_vs_meta_data = None


def _image_store_path(image_model: BaseEmbeddingModel | None, model_id: str | None) -> Path:
    """Resolve the store path: model-scoped when model_id is given, else legacy."""
    if model_id is not None:
        return model_scoped_vs_path(model_id, store_type="image")
    return IMAGE_VS_PATH


def _resolve_image_store_paths(
    image_model: BaseEmbeddingModel | None = None,
    model_id: str | None = None,
) -> tuple[Path, Path]:
    store = _image_store_path(image_model, model_id)
    return store, store / "meta_data.json"


def _load_saved_image_vs_metadata(image_model: BaseEmbeddingModel | None = None, model_id: str | None = None) -> dict:
    """Read persisted image-store metadata so the embedding dim can be recovered offline."""
    _, meta_path = _resolve_image_store_paths(image_model, model_id)
    if not meta_path.exists():
        return {}
    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _validate_image_store_model(meta_data: dict, image_model: BaseEmbeddingModel) -> None:
    """Raise if the store metadata belongs to a different image model."""
    model_ckpt = getattr(image_model, "CKPT", image_model.__class__.__name__)
    emb_dim = image_model.get_embedding_dim()

    if int(meta_data["_embedding_dim"]) != emb_dim:
        raise ValueError(
            f"Image vector store dimension mismatch: store={meta_data['_embedding_dim']} current={emb_dim}"
        )

    if meta_data["_model_ckpt"] != model_ckpt:
        raise ValueError(
            f"Image vector store model mismatch: store={meta_data['_model_ckpt']} current={model_ckpt}"
        )


def load_image_vector_store(
    image_model: BaseEmbeddingModel | None = None,
    model_id: str | None = None,
) -> tuple[faiss.Index, dict]:
    """Load the cached image vector store, creating it when no saved store exists.

    When ``model_id`` is provided the store is scoped to that model's namespace,
    otherwise the legacy ``IMAGE_VS_PATH`` is used.
    """
    global image_vs
    global image_vs_meta_data

    store_path, meta_path = _resolve_image_store_paths(image_model, model_id)

    if image_vs is not None and image_vs_meta_data is not None:
        if image_model is not None:
            _validate_image_store_model(image_vs_meta_data, image_model)
        return image_vs, image_vs_meta_data

    if not store_path.exists():
        if image_model is None:
            raise ValueError("Cannot create image vector store without image_model")

        image_vs, image_vs_meta_data = load_or_init_vector_store(
            str(store_path),
            emb_dim=image_model.get_embedding_dim(),
        )
        image_vs_meta_data["_embedding_dim"] = image_model.get_embedding_dim()
        image_vs_meta_data["_model_ckpt"] = getattr(image_model, "CKPT", image_model.__class__.__name__)
        if model_id is not None:
            image_vs_meta_data["_model_id"] = model_id
        save_image_vector_store()
        return image_vs, image_vs_meta_data

    saved_meta_data = _load_saved_image_vs_metadata(image_model, model_id)
    image_vs, image_vs_meta_data = load_or_init_vector_store(
        str(store_path),
        emb_dim=int(saved_meta_data["_embedding_dim"]),
    )
    if image_model is not None:
        _validate_image_store_model(image_vs_meta_data, image_model)
    return image_vs, image_vs_meta_data


def save_image_vector_store() -> None:
    """Persist the loaded image vector store and metadata to disk."""
    if image_vs is None or image_vs_meta_data is None:
        return
    raw_id = image_vs_meta_data.get("_model_id")
    if isinstance(raw_id, str):
        store = model_scoped_vs_path(raw_id, store_type="image")
    else:
        store = IMAGE_VS_PATH
    save_vs(image_vs, image_vs_meta_data, str(store))


def purge_image_entries(path: str | Path) -> dict[str, Any]:
    """Remove image vectors for an exact image path or for images under a directory.

    Reserved metadata keys are preserved, matching image ids are dropped, and
    the FAISS index is reconstructed from the vectors that remain. If every
    image is removed, the persisted vector store is deleted instead of keeping
    an empty file pair around.
    """
    global image_vs
    global image_vs_meta_data
    if not IMAGE_VS_PATH.exists():
        return {"removed_ids": [], "removed_count": 0, "remaining_count": 0}
    image_vs, image_vs_meta_data = load_image_vector_store()
    target_path = Path(canonicalize_path(path))
    target_key = canonicalize_path_key(target_path)

    removed_ids: list[int] = []
    kept_ids: list[int] = []
    next_meta_data = {
        str(key): value
        for key, value in image_vs_meta_data.items()
        if str(key).startswith("_")
    }

    for key, value in image_vs_meta_data.items():
        if str(key).startswith("_") or not isinstance(value, dict):
            continue
        image_path = value.get("image_path")

        should_remove = False
        if image_path and canonicalize_path_key(image_path) == target_key:
            should_remove = True
        elif image_path:
            try:
                Path(canonicalize_path(image_path)).relative_to(target_path)
                should_remove = True
            except ValueError:
                should_remove = False

        if should_remove:
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

    emb_dim = int(image_vs_meta_data["_embedding_dim"])
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
    image_vs_meta_data = next_meta_data
    save_image_vector_store()
    return {
        "removed_ids": removed_ids,
        "removed_count": len(removed_ids),
        "remaining_count": len(kept_ids),
    }

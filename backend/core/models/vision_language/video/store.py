import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np

from backend.config import VIDEO_VS_PATH, model_scoped_vs_path
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.utils.path_utils import canonicalize_path, canonicalize_path_key
from backend.utils.vector_store_utils import (
    create_empty_index,
    delete_vs,
    load_or_init_vector_store,
    save_vs,
)

video_vs = None
video_vs_meta_data = None


def get_loaded_video_vs_metadata() -> dict | None:
    """Return in-memory video metadata when the video store is loaded."""
    return video_vs_meta_data


def reset_video_vector_store() -> None:
    """Clear the in-memory video vector store so it reloads from disk next time."""
    global video_vs, video_vs_meta_data
    video_vs = None
    video_vs_meta_data = None


def _video_store_path(
    video_model: BaseEmbeddingModel | None, model_id: str | None
) -> Path:
    if model_id is not None:
        return model_scoped_vs_path(model_id, store_type="video")
    return VIDEO_VS_PATH


def _load_saved_video_vs_metadata(
    video_model: BaseEmbeddingModel | None = None,
    model_id: str | None = None,
) -> dict:
    """Read persisted video-store metadata so the embedding dim can be recovered offline."""
    store_dir = _video_store_path(video_model, model_id)
    meta_path = store_dir / "meta_data.json"
    if not meta_path.exists():
        return {}
    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _index_embedding_dim(vector_store: faiss.Index | None) -> int | None:
    """Return the embedding dimension from a loaded FAISS index when available."""
    if vector_store is None:
        return None
    emb_dim = getattr(vector_store, "d", None)
    if emb_dim is None:
        nested_index = getattr(vector_store, "index", None)
        emb_dim = getattr(nested_index, "d", None)
    return int(emb_dim) if emb_dim is not None else None


def _load_embedding_dim(
    saved_meta_data: dict, video_model: BaseEmbeddingModel | None
) -> int:
    """Resolve an embedding dimension before loading/creating a vector store."""
    saved_dim = saved_meta_data.get("_embedding_dim")
    if saved_dim is not None:
        return int(saved_dim)
    if video_model is not None:
        return video_model.get_embedding_dim()
    return 512


def _ensure_video_store_metadata(
    meta_data: dict,
    video_model: BaseEmbeddingModel | None,
    model_id: str | None,
    *,
    vector_store: faiss.Index | None = None,
) -> bool:
    """Backfill metadata fields required by model-scoped vector stores."""
    changed = False

    if "_embedding_dim" not in meta_data:
        emb_dim = (
            video_model.get_embedding_dim()
            if video_model is not None
            else _index_embedding_dim(vector_store)
        )
        meta_data["_embedding_dim"] = int(emb_dim or 512)
        changed = True

    if video_model is not None and "_model_ckpt" not in meta_data:
        meta_data["_model_ckpt"] = getattr(
            video_model, "CKPT", video_model.__class__.__name__
        )
        changed = True

    if model_id is not None and meta_data.get("_model_id") != model_id:
        meta_data["_model_id"] = model_id
        changed = True

    return changed


def _validate_video_store_model(
    meta_data: dict, video_model: BaseEmbeddingModel
) -> None:
    """Raise if the store metadata belongs to a different video model."""
    model_ckpt = getattr(video_model, "CKPT", video_model.__class__.__name__)
    emb_dim = video_model.get_embedding_dim()

    if int(meta_data["_embedding_dim"]) != emb_dim:
        raise ValueError(
            f"Video vector store dimension mismatch: store={meta_data['_embedding_dim']} current={emb_dim}"
        )

    if meta_data.get("_model_ckpt") != model_ckpt:
        raise ValueError(
            f"Video vector store model mismatch: store={meta_data.get('_model_ckpt')} current={model_ckpt}"
        )


def load_video_vector_store(
    video_model: BaseEmbeddingModel | None = None,
    model_id: str | None = None,
) -> tuple[faiss.Index, dict]:
    """Load the cached video vector store, creating it when no saved store exists.

    When ``model_id`` is provided the store is scoped to that model's namespace,
    otherwise the legacy ``VIDEO_VS_PATH`` is used.
    """
    global video_vs, video_vs_meta_data

    store_dir = _video_store_path(video_model, model_id)

    if video_vs is not None and video_vs_meta_data is not None:
        metadata_changed = _ensure_video_store_metadata(
            video_vs_meta_data,
            video_model,
            model_id,
            vector_store=video_vs,
        )
        if video_model is not None:
            _validate_video_store_model(video_vs_meta_data, video_model)
        if metadata_changed:
            save_video_vector_store()
        return video_vs, video_vs_meta_data

    index_path = store_dir / "index.faiss"
    meta_path = store_dir / "meta_data.json"
    store_exists = index_path.exists() and meta_path.exists()
    store_missing = not index_path.exists() and not meta_path.exists()

    if store_missing:
        if video_model is None:
            raise ValueError("Cannot create video vector store without video_model")

        video_vs, video_vs_meta_data = load_or_init_vector_store(
            str(store_dir),
            emb_dim=video_model.get_embedding_dim(),
        )
        _ensure_video_store_metadata(
            video_vs_meta_data,
            video_model,
            model_id,
            vector_store=video_vs,
        )
        save_video_vector_store()
        return video_vs, video_vs_meta_data

    if not store_exists:
        # Let the shared loader raise the existing, more specific incomplete-store error.
        video_vs, video_vs_meta_data = load_or_init_vector_store(
            str(store_dir),
            emb_dim=video_model.get_embedding_dim() if video_model is not None else 512,
        )
    else:
        saved_meta_data = _load_saved_video_vs_metadata(video_model, model_id)
        video_vs, video_vs_meta_data = load_or_init_vector_store(
            str(store_dir),
            emb_dim=_load_embedding_dim(saved_meta_data, video_model),
        )

    metadata_changed = _ensure_video_store_metadata(
        video_vs_meta_data,
        video_model,
        model_id,
        vector_store=video_vs,
    )
    if video_model is not None:
        _validate_video_store_model(video_vs_meta_data, video_model)
    if metadata_changed:
        save_video_vector_store()
    return video_vs, video_vs_meta_data


def save_video_vector_store() -> None:
    """Persist the loaded video vector store and metadata to disk."""
    if video_vs is None or video_vs_meta_data is None:
        return
    raw_id = video_vs_meta_data.get("_model_id")
    if isinstance(raw_id, str):
        store = model_scoped_vs_path(raw_id, store_type="video")
    else:
        store = VIDEO_VS_PATH
    save_vs(video_vs, video_vs_meta_data, str(store))


def purge_video_entries(path: str | Path) -> dict[str, Any]:
    """Remove video vectors for an exact video path or for videos under a directory.

    Reserved metadata keys are preserved, matching video ids are dropped, and
    the FAISS index is reconstructed from the vectors that remain. If every
    video is removed, the persisted vector store is deleted instead of keeping
    an empty file pair around.
    """
    global video_vs, video_vs_meta_data
    if not VIDEO_VS_PATH.exists():
        return {"removed_ids": [], "removed_count": 0, "remaining_count": 0}
    video_vs, video_vs_meta_data = load_video_vector_store()
    target_path = Path(canonicalize_path(path))
    target_key = canonicalize_path_key(target_path)

    removed_ids: list[int] = []
    kept_ids: list[int] = []
    next_meta_data = {
        str(key): value
        for key, value in video_vs_meta_data.items()
        if str(key).startswith("_")
    }

    for key, value in video_vs_meta_data.items():
        if str(key).startswith("_") or not isinstance(value, dict):
            continue
        video_path = value.get("video_path")

        should_remove = False
        if video_path and canonicalize_path_key(video_path) == target_key:
            should_remove = True
        elif video_path:
            try:
                Path(canonicalize_path(video_path)).relative_to(target_path)
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
        reset_video_vector_store()
        delete_vs(VIDEO_VS_PATH)
        return {
            "removed_ids": removed_ids,
            "removed_count": len(removed_ids),
            "remaining_count": 0,
        }

    emb_dim = int(video_vs_meta_data["_embedding_dim"])
    rebuilt_index = create_empty_index(emb_dim)
    rebuilt_vectors: list[np.ndarray] = []
    rebuilt_ids: list[int] = []
    for video_id in kept_ids:
        vector = np.empty((emb_dim,), dtype=np.float32)
        video_vs.reconstruct(int(video_id), vector)
        rebuilt_vectors.append(vector)
        rebuilt_ids.append(int(video_id))

    if rebuilt_vectors:
        add_with_ids = getattr(rebuilt_index, "add_with_ids")
        add_with_ids(
            np.asarray(rebuilt_vectors, dtype="float32"),
            np.asarray(rebuilt_ids, dtype=np.int64),
        )

    video_vs = rebuilt_index
    video_vs_meta_data = next_meta_data
    save_video_vector_store()
    return {
        "removed_ids": removed_ids,
        "removed_count": len(removed_ids),
        "remaining_count": len(kept_ids),
    }

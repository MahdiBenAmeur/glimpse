from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

import faiss
from backend.config import model_scoped_vs_path
from backend.utils.path_utils import canonicalize_path
from backend.utils.vector_store_utils import (
    create_empty_index,
    load_or_init_vector_store,
    save_vs,
)


_unified_vs: faiss.Index | None = None
_unified_vs_meta_data: dict[str, Any] | None = None


def reset_unified_vector_store() -> None:
    global _unified_vs, _unified_vs_meta_data
    _unified_vs = None
    _unified_vs_meta_data = None


def _unified_store_path(model_id: str) -> Path:
    return model_scoped_vs_path(model_id, store_type="unified")


def load_unified_vector_store(
    model_id: str,
    emb_dim: int = 512,
) -> tuple[faiss.Index, dict]:
    global _unified_vs, _unified_vs_meta_data

    if _unified_vs is not None and _unified_vs_meta_data is not None:
        return _unified_vs, _unified_vs_meta_data

    store_dir = _unified_store_path(model_id)
    _unified_vs, _unified_vs_meta_data = load_or_init_vector_store(
        store_dir, emb_dim=emb_dim,
    )
    _ensure_metadata_fields(_unified_vs_meta_data, model_id)
    return _unified_vs, _unified_vs_meta_data


def _ensure_metadata_fields(meta: dict, model_id: str) -> None:
    meta.setdefault("_model_ckpt", model_id)
    meta.setdefault("_model_id", model_id)
    meta.setdefault("_embedding_dim", 512)


def save_unified_vector_store() -> None:
    if _unified_vs is None or _unified_vs_meta_data is None:
        return
    store_dir = _unified_store_path(
        _unified_vs_meta_data.get("_model_id", "unknown")
    )
    save_vs(_unified_vs, _unified_vs_meta_data, store_dir)


def purge_unified_entries(path: str | Path) -> dict[str, Any]:
    global _unified_vs, _unified_vs_meta_data
    if _unified_vs is None or _unified_vs_meta_data is None:
        return {"removed_ids": [], "removed_count": 0, "remaining_count": 0}

    target_path = Path(canonicalize_path(path))
    target_key = canonicalize_path_key_for_unified(target_path)

    removed_ids: list[int] = []
    kept_ids: list[int] = []
    next_meta_data = {
        str(key): value
        for key, value in _unified_vs_meta_data.items()
        if str(key).startswith("_")
    }

    for key, value in _unified_vs_meta_data.items():
        if str(key).startswith("_") or not isinstance(value, dict):
            continue
        file_path = value.get("file_path")
        if not file_path:
            continue

        should_remove = False
        if canonicalize_path_key_for_unified(file_path) == target_key:
            should_remove = True
        else:
            try:
                Path(canonicalize_path(file_path)).relative_to(target_path)
                should_remove = True
            except ValueError:
                should_remove = False

        if should_remove:
            removed_ids.append(int(key))
        else:
            kept_ids.append(int(key))
            next_meta_data[str(key)] = value

    if not removed_ids:
        return {"removed_ids": [], "removed_count": 0, "remaining_count": len(kept_ids)}

    if not kept_ids:
        reset_unified_vector_store()
        return {"removed_ids": removed_ids, "removed_count": len(removed_ids), "remaining_count": 0}

    emb_dim = int(_unified_vs_meta_data.get("_embedding_dim", 512))
    rebuilt_index = create_empty_index(emb_dim)
    rebuilt_vectors: list[np.ndarray] = []
    rebuilt_ids: list[int] = []
    for item_id in kept_ids:
        rebuilt_vectors.append(_unified_vs.reconstruct(int(item_id)))
        rebuilt_ids.append(int(item_id))

    if rebuilt_vectors:
        rebuilt_index.add_with_ids(
            np.asarray(rebuilt_vectors, dtype="float32"),
            np.asarray(rebuilt_ids, dtype=np.int64),
        )

    _unified_vs = rebuilt_index
    _unified_vs_meta_data = next_meta_data
    save_unified_vector_store()
    return {
        "removed_ids": removed_ids,
        "removed_count": len(removed_ids),
        "remaining_count": len(kept_ids),
    }


def canonicalize_path_key_for_unified(path: str | Path) -> str:
    return canonicalize_path(path).lower()

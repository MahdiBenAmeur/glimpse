from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.config import (
    IMAGE_META_PATH,
    LIBRARY_STATE_PATH,
    VIDEO_META_PATH,
    model_scoped_vs_path,
)
from backend.core.models.vision_language.store import get_loaded_image_vs_metadata
from backend.core.models.vision_language.video.store import get_loaded_video_vs_metadata
from backend.utils.path_utils import canonicalize_path, canonicalize_path_key


def load_image_vs_meta_data(model_id: str | None = None) -> dict[str, Any]:
    """
    Loads image metadata from disk.
    """
    loaded_meta = get_loaded_image_vs_metadata()
    if isinstance(loaded_meta, dict) and loaded_meta:
        loaded_model_id = loaded_meta.get("_model_id")
        if model_id is None or loaded_model_id == model_id:
            return loaded_meta

    meta_path = (
        model_scoped_vs_path(model_id, "image") / "meta_data.json"
        if model_id is not None
        else IMAGE_META_PATH
    )
    if not meta_path.exists():
        return {}
    try:
        with meta_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def load_video_vs_meta_data() -> dict[str, Any]:
    """
    Loads video metadata from disk.
    """
    loaded_meta = get_loaded_video_vs_metadata()
    if isinstance(loaded_meta, dict) and loaded_meta:
        return loaded_meta
    if not VIDEO_META_PATH.exists():
        return {}
    try:
        with VIDEO_META_PATH.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def list_indexed_images() -> list[dict[str, Any]]:
    """
    Lists all indexed images.
    """
    meta_data = load_image_vs_meta_data()
    items: list[dict[str, Any]] = []
    for key, value in meta_data.items():
        if str(key).startswith("_") or not isinstance(value, dict):
            continue
        image_path = value.get("image_path")
        if not image_path:
            continue
        items.append(
            {
                "image_id": int(key),
                "image_path": canonicalize_path(image_path),
                "created_at": value.get("created_at"),
            }
        )
    items.sort(
        key=lambda item: (item.get("created_at") or "", item["image_id"]), reverse=True
    )
    return items


def get_indexed_image(image_id: int) -> dict[str, Any] | None:
    """
    Retrieves metadata for a specific indexed image.
    """
    image_entry = load_image_vs_meta_data().get(str(image_id))
    if not isinstance(image_entry, dict):
        return None
    image_path = image_entry.get("image_path")
    if not image_path:
        return None
    return {
        "image_id": int(image_id),
        "image_path": canonicalize_path(image_path),
        "created_at": image_entry.get("created_at"),
    }


def find_image_id_by_path(image_path: str | Path) -> int | None:
    """
    Finds an image ID by its file path.
    """
    resolved_key = canonicalize_path_key(image_path)
    for item in list_indexed_images():
        if canonicalize_path_key(item["image_path"]) == resolved_key:
            return int(item["image_id"])
    return None


def _default_state() -> dict[str, Any]:
    """
    Returns the default library state.
    """
    return {"images": {}}


def load_library_state() -> dict[str, Any]:
    """
    Loads the library state from disk.
    """
    if not LIBRARY_STATE_PATH.exists():
        return _default_state()
    try:
        with LIBRARY_STATE_PATH.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return _default_state()
    if not isinstance(loaded, dict):
        return _default_state()
    loaded.setdefault("images", {})
    return loaded


def save_library_state(state: dict[str, Any]) -> None:
    """
    Saves the library state to disk.
    """
    LIBRARY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LIBRARY_STATE_PATH.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def get_image_state(image_id: int) -> dict[str, Any]:
    """
    Retrieves the state for a specific image.
    """
    state = load_library_state()
    return state.get("images", {}).get(str(image_id), {})


def update_image_state(
    image_id: int,
    *,
    is_favorite: bool | None = None,
    collection_ids: list[int] | None = None,
) -> dict[str, Any]:
    """
    Updates the state for a specific image.
    """
    state = load_library_state()
    image_states = state.setdefault("images", {})
    current = dict(image_states.get(str(image_id), {}))

    if is_favorite is not None:
        current["is_favorite"] = bool(is_favorite)

    if collection_ids is not None:
        current["collection_ids"] = sorted(
            {int(collection_id) for collection_id in collection_ids}
        )

    image_states[str(image_id)] = current
    save_library_state(state)
    return current


def set_image_favorite(image_id: int, is_favorite: bool) -> dict[str, Any]:
    """
    Sets the favorite status of an image.
    """
    return update_image_state(image_id, is_favorite=is_favorite)


def get_image_collection_ids(image_id: int) -> list[int]:
    """
    Retrieves the collection IDs for an image.
    """
    return [
        int(collection_id)
        for collection_id in get_image_state(image_id).get("collection_ids", [])
    ]


def add_image_to_collection(image_id: int, collection_id: int) -> dict[str, Any]:
    """
    Adds an image to a collection.
    """
    collection_ids = set(get_image_collection_ids(image_id))
    collection_ids.add(int(collection_id))
    return update_image_state(image_id, collection_ids=sorted(collection_ids))


def remove_image_from_collection(image_id: int, collection_id: int) -> dict[str, Any]:
    """
    Removes an image from a collection.
    """
    collection_ids = [
        cid for cid in get_image_collection_ids(image_id) if cid != int(collection_id)
    ]
    return update_image_state(image_id, collection_ids=collection_ids)


def get_collection_image_ids(collection_id: int) -> list[int]:
    """
    Retrieves all image IDs in a collection.
    """
    state = load_library_state()
    result: list[int] = []
    for image_id, image_state in state.get("images", {}).items():
        if int(collection_id) in [
            int(cid) for cid in image_state.get("collection_ids", [])
        ]:
            result.append(int(image_id))
    return sorted(result)


def clear_collection(collection_id: int) -> None:
    """
    Removes all images from a collection.
    """
    state = load_library_state()
    updated = False
    for image_state in state.get("images", {}).values():
        current_ids = [int(cid) for cid in image_state.get("collection_ids", [])]
        next_ids = [cid for cid in current_ids if cid != int(collection_id)]
        if next_ids != current_ids:
            image_state["collection_ids"] = next_ids
            updated = True
    if updated:
        save_library_state(state)


def remove_image_states(image_ids: list[int]) -> int:
    """
    Removes the state records for multiple images.
    """
    if not image_ids:
        return 0

    state = load_library_state()
    image_states = state.setdefault("images", {})
    removed_count = 0
    for image_id in {int(image_id) for image_id in image_ids}:
        if image_states.pop(str(image_id), None) is not None:
            removed_count += 1

    if removed_count > 0:
        save_library_state(state)
    return removed_count

from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.store import load_image_vector_store
from backend.utils.vector_store_utils import consume_next_id


def coerce_image_paths(image_paths: Sequence[str | Path]) -> list[Path]:
    return [Path(path) for path in image_paths]


def prepare_image_paths(image_paths: Sequence[str | Path]) -> tuple[list[Path], list[dict]]:
    valid_paths: list[Path] = []
    failed_items: list[dict] = []

    for path in coerce_image_paths(image_paths):
        if not path.exists():
            failed_items.append({"path": str(path), "reason": "missing"})
            continue
        if not path.is_file():
            failed_items.append({"path": str(path), "reason": "not_a_file"})
            continue

        try:
            with Image.open(path) as image:
                image.verify()
        except Exception as exc:
            failed_items.append({"path": str(path), "reason": f"invalid_image: {exc}"})
            continue

        valid_paths.append(path)

    return valid_paths, failed_items


def index_image_batch(
    image_model: BaseEmbeddingModel,
    image_paths: Sequence[str | Path],
    *,
    validate_inputs: bool = True,
) -> dict:
    valid_paths, failed_items = prepare_image_paths(image_paths) if validate_inputs else (coerce_image_paths(image_paths), [])

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
    image_vector_store, image_store_meta_data = load_image_vector_store(int(embeddings.shape[1]), image_model)
    image_ids = [consume_next_id(image_store_meta_data) for _ in valid_paths]
    ids_array = np.array(image_ids, dtype=np.int64)
    embeddings_array = embeddings.numpy().astype("float32")

    image_vector_store.add_with_ids(embeddings_array, ids_array)

    for image_path, image_id in zip(valid_paths, image_ids):
        image_store_meta_data[str(image_id)] = {
            "image_path": str(image_path),
        }
        stats["indexed_ids"].append(image_id)

    stats["indexed_count"] = len(image_ids)
    stats["store_total"] = int(image_vector_store.ntotal)
    return stats

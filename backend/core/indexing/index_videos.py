from typing import Sequence

import numpy as np

from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.video.store import load_video_vector_store
from backend.utils.vector_store_utils import consume_next_id
from pathlib import Path


def index_video_batch(
    video_model: BaseEmbeddingModel,
    video_paths: Sequence[str | Path],
    *,
    path_2_created_at: dict[Path, str | None] | None = None,
    path_2_duration: dict[Path, float | None] | None = None,
) -> dict:
    stats = {
        "input_count": len(video_paths),
        "valid_count": len(video_paths),
        "failed_count": 0,
        "failed_items": [],
        "indexed_count": 0,
        "indexed_ids": [],
    }

    if not video_paths:
        return stats
    
    embeddings = video_model.embed_videos(video_paths)
    video_vector_store, video_store_meta_data = load_video_vector_store(video_model)
    video_ids = [consume_next_id(video_store_meta_data) for _ in video_paths]
    ids_array = np.array(video_ids, dtype=np.int64)
    embeddings_array = embeddings.numpy().astype("float32")

    video_vector_store.add_with_ids(embeddings_array, ids_array)

    for video_path, video_id in zip(video_paths, video_ids):
        entry = {
            "video_path": str(video_path),
            "created_at": path_2_created_at.get(video_path) if path_2_created_at is not None else None,
            "duration": path_2_duration.get(video_path) if path_2_duration is not None else None,
        }
        video_store_meta_data[str(video_id)] = entry
        stats["indexed_ids"].append(video_id)
    
    stats["indexed_count"] = len(video_ids)
    stats["store_total"] = int(video_vector_store.ntotal)
    return stats
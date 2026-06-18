from pathlib import Path
from typing import Sequence

import numpy as np

from backend.core.models.vision_language.unified_store import (
    load_unified_vector_store,
    save_unified_vector_store,
)
from backend.utils.vector_store_utils import consume_next_id


def index_video_batch(
    video_model,
    video_paths: Sequence[str | Path],
    *,
    path_2_created_at: dict[Path, str | None] | None = None,
    path_2_duration: dict[Path, float | None] | None = None,
    model_id: str | None = None,
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

    emb_dim = video_model.get_embedding_dim()
    resolved_model_id = model_id or "default"

    result = video_model.embed_video_keyframes(video_paths)
    embeddings = result["embeddings"]
    mapping = result["mapping"]

    vs, meta = load_unified_vector_store(resolved_model_id, emb_dim=emb_dim)
    total_rows = embeddings.shape[0]

    keyframe_ids = [consume_next_id(meta) for _ in range(total_rows)]
    ids_array = np.array(keyframe_ids, dtype=np.int64)
    embeddings_array = embeddings.numpy().astype("float32")

    vs.add_with_ids(embeddings_array, ids_array)

    for vinfo in mapping:
        video_path = vinfo["video_path"]
        start = vinfo["keyframe_start"]
        count = vinfo["keyframe_count"]
        created_at = (
            path_2_created_at.get(Path(video_path))
            if path_2_created_at is not None
            else None
        )
        duration = (
            path_2_duration.get(Path(video_path))
            if path_2_duration is not None
            else None
        )
        video_id = None
        for i in range(count):
            kid = keyframe_ids[start + i]
            if i == 0:
                video_id = kid
            meta[str(kid)] = {
                "file_path": video_path,
                "media_type": "video",
                "video_id": video_id,
                "keyframe_index": i,
                "total_keyframes": count,
                "created_at": created_at,
                "duration": duration,
            }
            stats["indexed_ids"].append(kid)

    save_unified_vector_store()
    stats["indexed_count"] = total_rows
    stats["store_total"] = int(vs.ntotal)
    return stats

from pathlib import Path
from datetime import datetime

import timm
import torch
import torch.nn.functional as F
from PIL import Image
from timm.data import create_transform, resolve_data_config

from backend.config import FACE_EMBEDDING_MODEL, FACE_EMBEDDING_MODEL_ID, DEVICE, MODELS_CACHE_DIR


def _log_face_embedding(message: str, **fields) -> None:
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    suffix = ""
    if fields:
        suffix = " | " + ", ".join(f"{key}={value!r}" for key, value in fields.items())
    print(f"[{timestamp}] [FACE EMBEDDING] {message}{suffix}", flush=True)


def _gpu_memory_snapshot() -> dict[str, float | int | str]:
    """Return lightweight CUDA memory counters for embedding logs."""
    if not torch.cuda.is_available():
        return {"cuda": "unavailable"}

    return {
        "allocated_mb": round(torch.cuda.memory_allocated() / (1024 * 1024), 2),
        "reserved_mb": round(torch.cuda.memory_reserved() / (1024 * 1024), 2),
        "max_allocated_mb": round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2),
        "max_reserved_mb": round(torch.cuda.max_memory_reserved() / (1024 * 1024), 2),
    }


def load_face_embedding_model():
    """Load and cache the face embedding model on the configured device."""
    global FACE_EMBEDDING_MODEL
    if FACE_EMBEDDING_MODEL is not None:
        return FACE_EMBEDDING_MODEL

    model_id = FACE_EMBEDDING_MODEL_ID
    model = timm.create_model(
        f"hf_hub:{model_id}",
        pretrained=True,
        cache_dir=MODELS_CACHE_DIR,

    ).to(DEVICE)
    model.eval()
    FACE_EMBEDDING_MODEL = model
    return model


def embed_faces(path_2_crops: dict[Path, list[Image.Image]], batch_size: int = 32) -> dict[Path, torch.Tensor]:
    """Convert face crops into normalized embedding tensors grouped by image path.

    Crops are flattened so the model can process them in efficient batches, but
    their source paths are kept in parallel. After inference the embeddings are
    L2-normalized on CPU and regrouped into one tensor per original image.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    if not path_2_crops:
        return {}

    model = load_face_embedding_model()
    data_config = resolve_data_config(model.pretrained_cfg, model=model)
    transform = create_transform(**data_config, is_training=False)

    path_2_embeddings = {image_path: [] for image_path in path_2_crops}
    flat_paths: list[Path] = []
    flat_crops = []

    for image_path, crops in path_2_crops.items():
        for crop in crops:
            flat_paths.append(image_path)
            flat_crops.append(transform(crop.convert("RGB")))

    if not flat_crops:
        return {
            image_path: torch.empty((0, 0), dtype=torch.float32)
            for image_path in path_2_crops
        }

    for start in range(0, len(flat_crops), batch_size):
        batch_paths = flat_paths[start : start + batch_size]
        _log_face_embedding(
            "Preparing face embedding batch",
            start=start,
            batch_item_count=len(batch_paths),
            total_face_count=len(flat_crops),
            **_gpu_memory_snapshot(),
        )
        batch = torch.stack(flat_crops[start : start + batch_size]).to(DEVICE)

        with torch.inference_mode():
            batch_embeddings = model(batch)

        batch_embeddings = F.normalize(batch_embeddings, dim=1).detach().cpu()
        _log_face_embedding(
            "Finished face embedding batch",
            start=start,
            batch_item_count=len(batch_paths),
            **_gpu_memory_snapshot(),
        )

        for image_path, embedding in zip(batch_paths, batch_embeddings):
            path_2_embeddings[image_path].append(embedding)

    # stacking embeddings per path for a final shape of [num_faces, embedding_dim] or an empty tensor if no faces were detected
    for image_path, embeddings in path_2_embeddings.items():
        if embeddings:
            path_2_embeddings[image_path] = torch.stack(embeddings)
        else:
            path_2_embeddings[image_path] = torch.empty((0, 0), dtype=torch.float32)

    return path_2_embeddings

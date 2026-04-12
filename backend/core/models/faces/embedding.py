from pathlib import Path

import timm
import torch
import torch.nn.functional as F
from PIL import Image
from timm.data import create_transform, resolve_data_config

from backend.config import FACE_EMBEDDING_MODEL, device, models_cache_dir


def load_face_embedding_model():
    global FACE_EMBEDDING_MODEL
    if FACE_EMBEDDING_MODEL is not None:
        return FACE_EMBEDDING_MODEL

    model_id = "gaunernst/vit_small_patch8_gap_112.cosface_ms1mv3"
    model = timm.create_model(
        f"hf_hub:{model_id}",
        pretrained=True,
        cache_dir=models_cache_dir,
    ).to(device)
    model.eval()
    FACE_EMBEDDING_MODEL = model
    return model


def embed_faces(path_2_crops: dict[Path, list[Image.Image]], batch_size: int = 32) -> dict[Path, torch.Tensor]:
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
        batch = torch.stack(flat_crops[start : start + batch_size]).to(device)

        with torch.inference_mode():
            batch_embeddings = model(batch)

        batch_embeddings = F.normalize(batch_embeddings, dim=1).detach().cpu()

        for image_path, embedding in zip(batch_paths, batch_embeddings):
            path_2_embeddings[image_path].append(embedding)

    for image_path, embeddings in path_2_embeddings.items():
        if embeddings:
            path_2_embeddings[image_path] = torch.stack(embeddings)
        else:
            path_2_embeddings[image_path] = torch.empty((0, 0), dtype=torch.float32)

    return path_2_embeddings

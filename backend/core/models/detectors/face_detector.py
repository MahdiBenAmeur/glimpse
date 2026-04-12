from pathlib import Path

from huggingface_hub import hf_hub_download
from PIL import Image
from ultralytics import YOLO

from backend.config import models_cache_dir, DETECTOR_MODEL

import torch.nn.functional as F
from PIL import Image
from timm.data import create_transform, resolve_data_config
import torch
from backend.config import device, models_cache_dir , FACE_EMBEDDING_MODEL
from backend.core.models.detectors.face_detector import crop_faces, detect_faces

import timm

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
            path_2_embeddings[image_path] =None

    return path_2_embeddings

    


def load_face_detector():
    global DETECTOR_MODEL
    if DETECTOR_MODEL is not None:
        return DETECTOR_MODEL
    model_path = hf_hub_download(
        repo_id="AdamCodd/YOLOv11n-face-detection",
        filename="model.pt",
        cache_dir=models_cache_dir,
    )

    model = YOLO(model_path)
    DETECTOR_MODEL = model
    return model


def detect_faces(image_paths: list[Path]):
    """
    takes in a list of image paths
    returns a dict mapping each image path to a list of bounding boxes (if any)
    """
    model = load_face_detector()
    sources = [str(path) for path in image_paths]
    results = model.predict(sources, save=False)
    path_2_boxes = {}
    for image_path, result in zip(image_paths, results):
        if result.boxes is not None:
            path_2_boxes[image_path] = result.boxes
    return path_2_boxes

def crop_faces(path_2_boxes)-> dict[Path, list[Image.Image]]:
    path_2_crops = {}
    for image_path, boxes in path_2_boxes.items():
        image = Image.open(image_path)
        crops = []
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            crop = image.crop((x1, y1, x2, y2))
            crops.append(crop)
        path_2_crops[image_path] = crops
    return path_2_crops


"""

image_paths = [
    Path("image.png"),
]

sources = [str(path) for path in image_paths]
results = model.predict(sources, save=False)

for image_path, result in zip(image_paths, results):
    print(f"\nImage: {image_path}")
    print(result)

    if result.boxes is not None:
        for index, box in enumerate(result.boxes, start=1):
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            confidence = float(box.conf[0]) if box.conf is not None else 0.0
            print(
                f"Box {index}: "
                f"({x1:.1f}, {y1:.1f}) -> ({x2:.1f}, {y2:.1f}) "
                f"confidence={confidence:.3f}"
            )
    else:
        print("No boxes detected.")

    annotated_bgr = result.plot()
    annotated_rgb = annotated_bgr[..., ::-1]
    annotated_image = Image.fromarray(annotated_rgb)
    annotated_image.show(title=f"Detection Result - {image_path.name}")
"""
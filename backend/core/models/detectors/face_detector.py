import json
from pathlib import Path

from huggingface_hub import hf_hub_download
from PIL import Image
from ultralytics import YOLO

import torch.nn.functional as F
from timm.data import create_transform, resolve_data_config
import torch

from backend.config import (
    DETECTOR_MODEL,
    FACE_EMBEDDING_MODEL,
    FACE_MERGE_THRESHOLD,
    FACE_VS_PATH,
    PERSON_VS_PATH,
    device,
    models_cache_dir,
)
import numpy as np
import timm
import faiss
from backend.utils.vector_store_utils import load_or_init_vector_store  , consume_next_id

face_emb_dim = 512
face_vs = None
face_meta_data = None
person_vs = None
person_meta_data = None






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
            path_2_embeddings[image_path] =torch.empty((0, 0), dtype=torch.float32)

    return path_2_embeddings



def load_face_vector_store():
    global face_vs
    global face_meta_data
    if face_vs is not None and face_meta_data is not None:
        return face_vs, face_meta_data

    face_vs, face_meta_data = load_or_init_vector_store(FACE_VS_PATH , emb_dim=face_emb_dim)
    return face_vs, face_meta_data

def load_person_vector_store():
    global person_vs
    global person_meta_data
    if person_vs is not None and person_meta_data is not None:
        return person_vs, person_meta_data

    person_vs, person_meta_data = load_or_init_vector_store(PERSON_VS_PATH , emb_dim=face_emb_dim)
    return person_vs, person_meta_data



def _embedding_row(embedding: torch.Tensor) -> np.ndarray:
    return embedding.unsqueeze(0).cpu().numpy().astype("float32")


def _update_person_centroid(person_id: int, embedding: torch.Tensor, person_meta_data: dict, person_vs) -> None:
    person_key = str(person_id)
    person_entry = person_meta_data[person_key]
    previous_count = int(person_entry["count"])
    previous_centroid = torch.tensor(person_entry["centroid"], dtype=torch.float32)

    updated_centroid = ((previous_centroid * previous_count) + embedding) / (previous_count + 1)
    updated_centroid = F.normalize(updated_centroid.unsqueeze(0), dim=1).squeeze(0).cpu()

    person_vs.remove_ids(np.array([person_id], dtype=np.int64))
    person_vs.add_with_ids(
        updated_centroid.unsqueeze(0).numpy().astype("float32"),
        np.array([person_id], dtype=np.int64),
    )

    person_entry["count"] = previous_count + 1
    person_entry["centroid"] = updated_centroid.tolist()





def add_faces_to_vector_store(path_2_embeddings: dict[Path, torch.Tensor], path_2_boxes: dict[Path, list]):
    face_vs, face_meta_data = load_face_vector_store()
    person_vs, person_meta_data = load_person_vector_store()
    for image_path, embeddings in path_2_embeddings.items():
        for i, embedding in enumerate(embeddings):
            embedding_row = _embedding_row(embedding)
            face_box = path_2_boxes[image_path][i].xyxy[0].tolist()

            if person_vs.ntotal == 0:
                person_id = consume_next_id(person_meta_data)
                person_vs.add_with_ids(embedding_row, np.array([person_id], dtype=np.int64))
                person_meta_data[str(person_id)] = {
                    "count": 1,
                    "centroid": embedding.tolist(),
                    "image_paths": [str(image_path)],
                    "face_boxes": [face_box],
                }
            else:
                scores, ids = person_vs.search(embedding_row, k=1)
                best_score = float(scores[0][0])
                person_id = int(ids[0][0])

                if best_score < FACE_MERGE_THRESHOLD or person_id < 0:
                    person_id = consume_next_id(person_meta_data)
                    person_vs.add_with_ids(embedding_row, np.array([person_id], dtype=np.int64))
                    person_meta_data[str(person_id)] = {
                        "count": 1,
                        "centroid": embedding.tolist(),
                        "image_paths": [str(image_path)],
                        "face_boxes": [face_box],
                    }
                else:
                    _update_person_centroid(person_id, embedding, person_meta_data, person_vs)
                    person_meta_data[str(person_id)]["image_paths"].append(str(image_path))
                    person_meta_data[str(person_id)]["face_boxes"].append(face_box)

            face_id = consume_next_id(face_meta_data)
            face_vs.add_with_ids(embedding_row, np.array([face_id], dtype=np.int64))
            face_meta_data[str(face_id)] = {
                "person_id": person_id,
                "image_path": str(image_path),
                "face_box": face_box,
            }



    


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
    results = model.predict(image_paths, save=False)
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



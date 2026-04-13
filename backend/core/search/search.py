from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from backend.core.models.faces.detector import crop_faces, detect_faces
from backend.core.models.faces.embedding import embed_faces
from backend.core.models.faces.store import load_person_vector_store
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.store import load_image_vector_store
from backend.utils.vector_store_utils import embedding_row


def _validate_top_k(top_k: int) -> int:
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")
    return int(top_k)

def _collect_image_matches(scores: np.ndarray, ids: np.ndarray, image_meta_data: dict) -> list[dict]:
    matches = []
    for score, item_id in zip(scores[0], ids[0]):
        item_id = int(item_id)
        if item_id < 0:
            continue

        meta_entry = image_meta_data.get(str(item_id), {})
        matches.append(
            {
                "image_id": item_id,
                "score": float(score),
                "image_path": meta_entry.get("image_path"),
            }
        )
    return matches


def _collect_person_matches(scores: np.ndarray, ids: np.ndarray, person_meta_data: dict) -> list[dict]:
    matches = []
    for score, person_id in zip(scores[0], ids[0]):
        person_id = int(person_id)
        if person_id < 0:
            continue

        meta_entry = person_meta_data.get(str(person_id), {})
        matches.append(
            {
                "person_id": person_id,
                "score": float(score),
                "count": meta_entry.get("count"),
                "image_paths": meta_entry.get("image_paths", []),
                "face_boxes": meta_entry.get("face_boxes", []),
            }
        )
    return matches


def search_by_text(text: str, image_model: BaseEmbeddingModel, top_k: int = 10) -> list[dict]:
    if not text.strip():
        raise ValueError("text must not be empty")

    top_k = _validate_top_k(top_k)
    text_embedding = image_model.embed_text(text)
    emb_dim = int(text_embedding.shape[-1])
    image_vs, image_meta_data = load_image_vector_store(emb_dim, image_model)

    if image_vs.ntotal == 0:
        return []

    k = min(top_k, int(image_vs.ntotal))
    scores, ids = image_vs.search(embedding_row(text_embedding), k=k)
    return _collect_image_matches(scores, ids, image_meta_data)


def search_by_image(
    image: str | Path | Image.Image,
    image_model: BaseEmbeddingModel,
    top_k: int = 10,
) -> list[dict]:
    top_k = _validate_top_k(top_k)
    image_embedding = image_model.embed_image(image)
    emb_dim = int(image_embedding.shape[-1])
    image_vs, image_meta_data = load_image_vector_store(emb_dim, image_model)

    if image_vs.ntotal == 0:
        return []

    k = min(top_k, int(image_vs.ntotal))
    scores, ids = image_vs.search(embedding_row(image_embedding), k=k)
    return _collect_image_matches(scores, ids, image_meta_data)


def search_by_face(image_path: str | Path, top_k: int = 10) -> list[dict]:
    top_k = _validate_top_k(top_k)
    query_path = Path(image_path)
    if not query_path.is_file():
        raise FileNotFoundError(f"Image not found: {query_path}")

    path_2_boxes = detect_faces([query_path])
    boxes = path_2_boxes.get(query_path)
    if boxes is None or len(boxes) == 0:
        return []

    path_2_crops = crop_faces({query_path: boxes})
    path_2_embeddings = embed_faces(path_2_crops, batch_size=len(path_2_crops[query_path]))
    query_embeddings = path_2_embeddings.get(query_path)
    if query_embeddings is None or query_embeddings.numel() == 0:
        return []

    person_vs, person_meta_data = load_person_vector_store()
    if person_vs.ntotal == 0:
        return []

    k = min(top_k, int(person_vs.ntotal))
    results = []

    for face_index, embedding in enumerate(query_embeddings):
        scores, ids = person_vs.search(embedding_row(embedding), k=k)
        results.append(
            {
                "query_image_path": str(query_path),
                "query_face_index": face_index,
                "query_face_box": boxes[face_index].xyxy[0].tolist(),
                "matches": _collect_person_matches(scores, ids, person_meta_data),
            }
        )

    return results

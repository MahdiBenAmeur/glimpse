from pathlib import Path

import faiss
import numpy as np
import torch
import torch.nn.functional as F

from backend.config import FACE_MERGE_THRESHOLD, FACE_VS_PATH, PERSON_VS_PATH
from backend.utils.vector_store_utils import consume_next_id, load_or_init_vector_store, save_vs


face_emb_dim = 512
face_vs = None
face_meta_data = None
person_vs = None
person_meta_data = None


def load_face_vector_store():
    global face_vs
    global face_meta_data
    if face_vs is not None and face_meta_data is not None:
        return face_vs, face_meta_data

    face_vs, face_meta_data = load_or_init_vector_store(FACE_VS_PATH, emb_dim=face_emb_dim)
    return face_vs, face_meta_data


def load_person_vector_store():
    global person_vs
    global person_meta_data
    if person_vs is not None and person_meta_data is not None:
        return person_vs, person_meta_data

    person_vs, person_meta_data = load_or_init_vector_store(PERSON_VS_PATH, emb_dim=face_emb_dim)
    return person_vs, person_meta_data


def save_face_vector_stores() -> None:
    face_vector_store, face_store_meta_data = load_face_vector_store()
    person_vector_store, person_store_meta_data = load_person_vector_store()
    save_vs(face_vector_store, face_store_meta_data, FACE_VS_PATH)
    save_vs(person_vector_store, person_store_meta_data, PERSON_VS_PATH)


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
    stats = {
        "indexed_face_count": 0,
        "new_person_count": 0,
        "assigned_person_ids": [],
    }

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
                stats["new_person_count"] += 1
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
                    stats["new_person_count"] += 1
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
            stats["indexed_face_count"] += 1
            stats["assigned_person_ids"].append(person_id)

    stats["assigned_person_ids"] = sorted(set(stats["assigned_person_ids"]))
    stats["assigned_person_count"] = len(stats["assigned_person_ids"])
    stats["person_store_total"] = int(person_vs.ntotal)
    stats["face_store_total"] = int(face_vs.ntotal)
    return stats

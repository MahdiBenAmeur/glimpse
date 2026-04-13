import faiss
import json
import numpy as np
import shutil
from pathlib import Path
import torch


def create_empty_index(emb_dim=512):
    base_index = faiss.IndexFlatIP(emb_dim)
    return faiss.IndexIDMap2(base_index)


def load_or_init_vector_store(vs_path: str , emb_dim=512):
    store_dir = Path(vs_path)
    store_dir.mkdir(parents=True, exist_ok=True)

    index_path = store_dir / "index.faiss"
    meta_data_path = store_dir / "meta_data.json"

    if not index_path.exists() and not meta_data_path.exists():
        vector_store = create_empty_index(emb_dim)
        meta_data = {"_next_id": 0}
        faiss.write_index(vector_store, str(index_path))
        with open(meta_data_path, "w") as f:
            json.dump(meta_data, f)
        return vector_store, meta_data

    if not index_path.exists() or not meta_data_path.exists():
        raise FileNotFoundError(f"Incomplete vector store at {store_dir}")

    vector_store = faiss.read_index(str(index_path))
    with open(meta_data_path, "r") as f:
        meta_data = json.load(f)

    if not isinstance(meta_data, dict):
        raise ValueError(f"Invalid metadata format at {meta_data_path}")

    if "_next_id" not in meta_data:
        existing_ids = [int(key) for key in meta_data.keys()]
        meta_data["_next_id"] = (max(existing_ids) + 1) if existing_ids else 0

    return vector_store, meta_data




def consume_next_id(meta_data: dict) -> int:
    next_id = int(meta_data["_next_id"])
    meta_data["_next_id"] = next_id + 1
    return next_id


def embedding_row(embedding: torch.Tensor) -> np.ndarray:
    return embedding.unsqueeze(0).cpu().numpy().astype("float32")


def save_vs(vs, meta_data, vs_path):
    index_path = Path(vs_path) / "index.faiss"
    meta_data_path = Path(vs_path) / "meta_data.json"
    faiss.write_index(vs, str(index_path))
    with open(meta_data_path, "w") as f:
        json.dump(meta_data, f)


def delete_vs(vs_path):
    store_dir = Path(vs_path)
    if store_dir.exists():
        shutil.rmtree(store_dir)

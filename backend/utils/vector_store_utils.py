from datetime import datetime
import faiss
import json
import numpy as np
from pathlib import Path
import shutil
import threading
import traceback
import torch


def _vector_store_call_site(limit: int = 4) -> str:
    frames = traceback.extract_stack()[:-2]
    relevant = [frame for frame in frames if "backend" in frame.filename.replace("\\", "/")]
    tail = relevant[-limit:] if relevant else frames[-limit:]
    return " <- ".join(
        f"{Path(frame.filename).as_posix()}:{frame.lineno}:{frame.name}"
        for frame in tail
    )


def _log_vector_store(message: str, **fields) -> None:
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    thread = threading.current_thread()
    payload = {
        "thread_name": thread.name,
        "thread_ident": thread.ident,
        **fields,
    }
    suffix = ""
    if payload:
        suffix = " | " + ", ".join(f"{key}={value!r}" for key, value in payload.items())
    print(f"[{timestamp}] [VECTOR STORE] {message}{suffix}", flush=True)


def create_empty_index(emb_dim=512):
    base_index = faiss.IndexFlatIP(emb_dim)
    return faiss.IndexIDMap2(base_index)


def load_or_init_vector_store(vs_path: str , emb_dim=512):
    store_dir = Path(vs_path)
    _log_vector_store(
        "load_or_init_vector_store called",
        vs_path=str(store_dir),
        emb_dim=emb_dim,
        exists=store_dir.exists(),
        call_site=_vector_store_call_site(),
    )
    store_dir.mkdir(parents=True, exist_ok=True)

    index_path = store_dir / "index.faiss"
    meta_data_path = store_dir / "meta_data.json"

    if not index_path.exists() and not meta_data_path.exists():
        _log_vector_store(
            "Initializing empty vector store",
            vs_path=str(store_dir),
            index_exists=index_path.exists(),
            metadata_exists=meta_data_path.exists(),
        )
        vector_store = create_empty_index(emb_dim)
        meta_data = {"_next_id": 0}
        faiss.write_index(vector_store, str(index_path))
        with open(meta_data_path, "w") as f:
            json.dump(meta_data, f)
        _log_vector_store(
            "Initialized empty vector store",
            vs_path=str(store_dir),
            ntotal=int(vector_store.ntotal),
        )
        return vector_store, meta_data

    if not index_path.exists() or not meta_data_path.exists():
        _log_vector_store(
            "Detected incomplete vector store",
            vs_path=str(store_dir),
            index_exists=index_path.exists(),
            metadata_exists=meta_data_path.exists(),
        )
        raise FileNotFoundError(f"Incomplete vector store at {store_dir}")

    vector_store = faiss.read_index(str(index_path))
    with open(meta_data_path, "r") as f:
        meta_data = json.load(f)

    if not isinstance(meta_data, dict):
        raise ValueError(f"Invalid metadata format at {meta_data_path}")

    if "_next_id" not in meta_data:
        existing_ids = [int(key) for key in meta_data.keys()]
        meta_data["_next_id"] = (max(existing_ids) + 1) if existing_ids else 0

    _log_vector_store(
        "Loaded vector store",
        vs_path=str(store_dir),
        ntotal=int(vector_store.ntotal),
        metadata_entry_count=len(meta_data),
        next_id=meta_data.get("_next_id"),
    )
    return vector_store, meta_data




def consume_next_id(meta_data: dict) -> int:
    next_id = int(meta_data["_next_id"])
    meta_data["_next_id"] = next_id + 1
    return next_id


def embedding_row(embedding: torch.Tensor) -> np.ndarray:
    return embedding.unsqueeze(0).cpu().numpy().astype("float32")


def save_vs(vs, meta_data, vs_path):
    store_dir = Path(vs_path)
    _log_vector_store(
        "Saving vector store",
        vs_path=str(store_dir),
        ntotal=int(vs.ntotal),
        metadata_entry_count=len(meta_data),
        next_id=meta_data.get("_next_id"),
        call_site=_vector_store_call_site(),
    )
    store_dir.mkdir(parents=True, exist_ok=True)
    index_path = store_dir / "index.faiss"
    meta_data_path = store_dir / "meta_data.json"
    faiss.write_index(vs, str(index_path))
    with open(meta_data_path, "w") as f:
        json.dump(meta_data, f)
    _log_vector_store(
        "Saved vector store",
        vs_path=str(store_dir),
        index_exists=index_path.exists(),
        metadata_exists=meta_data_path.exists(),
    )


def delete_vs(vs_path):
    store_dir = Path(vs_path)
    _log_vector_store(
        "Deleting vector store directory",
        vs_path=str(store_dir),
        exists=store_dir.exists(),
        call_site=_vector_store_call_site(),
    )
    if store_dir.exists():
        try:
            shutil.rmtree(store_dir)
        except Exception as exc:
            entries = []
            try:
                entries = sorted(path.name for path in store_dir.iterdir())
            except Exception as list_exc:
                entries = [f"<could not list dir: {list_exc}>"]
            _log_vector_store(
                "Deleting vector store directory failed",
                vs_path=str(store_dir),
                error=str(exc),
                dir_entries=entries,
            )
            raise
    _log_vector_store(
        "Delete vector store directory finished",
        vs_path=str(store_dir),
        exists_after=store_dir.exists(),
    )

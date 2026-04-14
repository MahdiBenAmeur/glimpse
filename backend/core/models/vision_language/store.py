import faiss

from backend.config import IMAGE_VS_PATH
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.utils.vector_store_utils import load_or_init_vector_store, save_vs


image_vs = None
image_meta_data = None


def get_loaded_image_metadata() -> dict | None:
    return image_meta_data


def reset_image_vector_store() -> None:
    global image_vs
    global image_meta_data
    image_vs = None
    image_meta_data = None


def _ensure_image_store_metadata(meta_data: dict, image_model: BaseEmbeddingModel, emb_dim: int) -> None:
    model_ckpt = getattr(image_model, "CKPT", image_model.__class__.__name__)

    if "_embedding_dim" not in meta_data:
        meta_data["_embedding_dim"] = emb_dim
    elif int(meta_data["_embedding_dim"]) != emb_dim:
        raise ValueError(
            f"Image vector store dimension mismatch: store={meta_data['_embedding_dim']} current={emb_dim}"
        )

    if "_model_ckpt" not in meta_data:
        meta_data["_model_ckpt"] = model_ckpt
    elif meta_data["_model_ckpt"] != model_ckpt:
        raise ValueError(
            f"Image vector store model mismatch: store={meta_data['_model_ckpt']} current={model_ckpt}"
        )


def load_image_vector_store(emb_dim: int, image_model: BaseEmbeddingModel) -> tuple[faiss.Index, dict]:
    global image_vs
    global image_meta_data

    if image_vs is not None and image_meta_data is not None:
        _ensure_image_store_metadata(image_meta_data, image_model, emb_dim)
        return image_vs, image_meta_data

    image_vs, image_meta_data = load_or_init_vector_store(IMAGE_VS_PATH, emb_dim=emb_dim)
    _ensure_image_store_metadata(image_meta_data, image_model, emb_dim)
    return image_vs, image_meta_data


def save_image_vector_store() -> None:
    if image_vs is None or image_meta_data is None:
        return
    save_vs(image_vs, image_meta_data, IMAGE_VS_PATH)

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Sequence

import huggingface_hub.constants as hf_constants
import torch
from PIL import Image
import transformers.utils.hub as transformers_hub_utils
from transformers import AutoModel, AutoProcessor

from backend.config import device
from backend.core.models.vision_language.base import BaseEmbeddingModel


@contextmanager
def _temporary_hf_offline():
    original_values = {
        "HF_HUB_OFFLINE": os.environ.get("HF_HUB_OFFLINE"),
        "TRANSFORMERS_OFFLINE": os.environ.get("TRANSFORMERS_OFFLINE"),
    }
    original_hf_hub_offline = hf_constants.HF_HUB_OFFLINE
    had_transformers_hub_offline = hasattr(transformers_hub_utils, "HF_HUB_OFFLINE")
    original_transformers_hub_offline = getattr(transformers_hub_utils, "HF_HUB_OFFLINE", None)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    hf_constants.HF_HUB_OFFLINE = True
    setattr(transformers_hub_utils, "HF_HUB_OFFLINE", True)
    try:
        yield
    finally:
        hf_constants.HF_HUB_OFFLINE = original_hf_hub_offline
        if had_transformers_hub_offline:
            setattr(transformers_hub_utils, "HF_HUB_OFFLINE", original_transformers_hub_offline)
        else:
            delattr(transformers_hub_utils, "HF_HUB_OFFLINE")
        for key, value in original_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class QwenEmbeddingModel(BaseEmbeddingModel):
    CKPT = "Qwen/Qwen3-VL-Embedding-2B"
    processor_class = AutoProcessor
    model_class = AutoModel
    processor_load_kwargs = {"trust_remote_code": True}
    model_load_kwargs = {"trust_remote_code": True}

    def load_model(self):
        if self._processor is not None and self._model is not None:
            return self._processor, self._model

        if not self.is_model_downloaded():
            self.download_model()

        with _temporary_hf_offline():
            self._processor = self._load_processor(local_files_only=True)
            self._model = self._load_model(local_files_only=True).to(device)
        self._model.eval()
        return self._processor, self._model

    def embed_images(self, images: Sequence[str | Path | Image.Image]) -> torch.Tensor:
        self._validate_images(images)

        processor, model = self.load_model()
        pil_images = [self._to_pil_image(image) for image in images]
        image_inputs = processor.image_processor(images=pil_images, return_tensors="pt")
        image_inputs = {name: tensor.to(device) for name, tensor in image_inputs.items()}

        with torch.inference_mode():
            vision_output = model.get_image_features(**image_inputs)

        image_feature_groups = getattr(vision_output, "pooler_output", ())
        pooled_embeddings = torch.stack(
            [
                image_features.mean(dim=0) if image_features.ndim > 1 else image_features
                for image_features in image_feature_groups
            ]
        )

        return self._normalize_embeddings(pooled_embeddings)

    def embed_texts(self, texts: Sequence[str]) -> torch.Tensor:
        self._validate_texts(texts)

        processor, model = self.load_model()
        text_inputs = processor.tokenizer(
            list(texts),
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        text_inputs = {name: tensor.to(device) for name, tensor in text_inputs.items()}

        with torch.inference_mode():
            outputs = model(**text_inputs, return_dict=True)

        token_embeddings = outputs.last_hidden_state
        attention_mask = text_inputs.get("attention_mask")
        if attention_mask is None:
            pooled_embeddings = token_embeddings.mean(dim=1)
        else:
            mask = attention_mask.unsqueeze(-1).to(token_embeddings.dtype)
            pooled_embeddings = (token_embeddings * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)

        return self._normalize_embeddings(pooled_embeddings)

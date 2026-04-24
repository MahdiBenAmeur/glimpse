from __future__ import annotations

from pathlib import Path
from typing import Sequence

import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.config import device


class SiglipEmbeddingModel(BaseEmbeddingModel):
    CKPT = "google/siglip2-base-patch16-224"
    processor_class = AutoProcessor
    model_class = AutoModel

    def embed_images(self, images: Sequence[str | Path | Image.Image]) -> torch.Tensor:
        self._validate_images(images)

        processor, model = self.load_model()
        pil_images = [self._to_pil_image(image) for image in images]
        inputs = processor(images=pil_images, return_tensors="pt" , device=device)

        with torch.inference_mode():
            image_features = model.get_image_features(**inputs)

        return self._normalize_embeddings(_coerce_siglip_features(image_features))

    def embed_texts(self, texts: Sequence[str]) -> torch.Tensor:
        self._validate_texts(texts)

        processor, model = self.load_model()
        inputs = processor(
            text=list(texts),
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        inputs = {name: tensor.to(device) for name, tensor in inputs.items()}

        with torch.inference_mode():
            text_features = model.get_text_features(**inputs)

        return self._normalize_embeddings(_coerce_siglip_features(text_features))


class SiglipLargeEmbeddingModel(SiglipEmbeddingModel):
    CKPT = "google/siglip2-large-patch16-384"


def _coerce_siglip_features(output) -> torch.Tensor:
    if isinstance(output, torch.Tensor):
        return output

    pooled_output = getattr(output, "pooler_output", None)
    if isinstance(pooled_output, torch.Tensor):
        return pooled_output

    raise TypeError(
        "SigLIP feature output did not match the expected contract. "
        f"Expected a tensor or an object with pooler_output, got {type(output).__name__}."
    )

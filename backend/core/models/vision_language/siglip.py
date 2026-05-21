from __future__ import annotations

from pathlib import Path
from typing import Sequence

import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

from backend.core.models.vision_language.base import BaseEmbeddingModel


class SiglipEmbeddingModel(BaseEmbeddingModel):
    CKPT = "google/siglip2-base-patch16-224"
    embedding_dim = 768
    processor_class = AutoProcessor
    model_class = AutoModel

    def embed_images(self, images: Sequence[str | Path | Image.Image]) -> torch.Tensor:
        """Encode images with SigLIP and return normalized image embeddings."""
        self._validate_images(images)

        processor, model = self.load_model()
        pil_images = [self._to_pil_image(image) for image in images]
        inputs = processor(images=pil_images, return_tensors="pt")
        del pil_images
        inputs = self._move_inputs_to_device(inputs)

        with torch.inference_mode():
            image_features = model.get_image_features(**inputs)

        return self._normalize_embeddings(image_features.pooler_output)

    def embed_texts(self, texts: Sequence[str]) -> torch.Tensor:
        """Encode texts with SigLIP and return normalized text embeddings."""
        self._validate_texts(texts)

        processor, model = self.load_model()
        inputs = processor(
            text=list(texts),
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        inputs = self._move_inputs_to_device(inputs)

        with torch.inference_mode():
            text_features = model.get_text_features(**inputs)

        return self._normalize_embeddings(text_features.pooler_output)


class SiglipLargeEmbeddingModel(SiglipEmbeddingModel):
    CKPT = "google/siglip2-large-patch16-384"
    embedding_dim = 1024

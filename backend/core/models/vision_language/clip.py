from __future__ import annotations

from pathlib import Path
from typing import Sequence

import torch
from PIL import Image
from transformers import AutoProcessor, CLIPModel

from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.config import device


class ClipEmbeddingModel(BaseEmbeddingModel):
    CKPT = "openai/clip-vit-base-patch32"
    processor_class = AutoProcessor
    model_class = CLIPModel

    def embed_images(self, images: Sequence[str | Path | Image.Image]) -> torch.Tensor:
        self._validate_images(images)

        processor, model = self.load_model()
        pil_images = [self._to_pil_image(image) for image in images]
        inputs = processor(images=pil_images, return_tensors="pt")
        inputs = {name: tensor.to(device) for name, tensor in inputs.items()}

        with torch.inference_mode():
            image_features = model.get_image_features(**inputs)

        return self._normalize_embeddings(image_features)

    def embed_texts(self, texts: Sequence[str]) -> torch.Tensor:
        self._validate_texts(texts)

        processor, model = self.load_model()
        inputs = processor(
            text=list(texts),
            padding=True,
            truncation=True,
            return_tensors="pt",
        )
        inputs = {name: tensor.to(device) for name, tensor in inputs.items()}

        with torch.inference_mode():
            text_features = model.get_text_features(**inputs)

        return self._normalize_embeddings(text_features)

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

from backend.core.models.embedders.base import BaseEmbeddingModel


class QwenEmbeddingModel(BaseEmbeddingModel):
    CKPT = "Qwen/Qwen3-VL-Embedding-2B"
    processor_class = AutoProcessor
    model_class = AutoModel
    processor_load_kwargs = {"trust_remote_code": True}
    model_load_kwargs = {"trust_remote_code": True}

    def embed_images(self, images: Sequence[str | Path | Image.Image]) -> torch.Tensor:
        self._validate_images(images)

        processor, model = self.load_model()
        inputs = [{"image": self._to_pil_image(image)} for image in images]

        with torch.inference_mode():
            embeddings = model.encode(inputs, processor=processor)

        return self._normalize_embeddings(embeddings)

    def embed_texts(self, texts: Sequence[str]) -> torch.Tensor:
        self._validate_texts(texts)

        processor, model = self.load_model()
        inputs = [{"text": text} for text in texts]

        with torch.inference_mode():
            embeddings = model.encode(inputs, processor=processor)

        return self._normalize_embeddings(embeddings)

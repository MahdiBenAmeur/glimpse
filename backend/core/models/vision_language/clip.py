from __future__ import annotations

from pathlib import Path
from typing import Sequence

import torch
from PIL import Image
from transformers import AutoProcessor, CLIPModel

from backend.core.models.vision_language.base import BaseEmbeddingModel


class ClipEmbeddingModel(BaseEmbeddingModel):
    CKPT = "openai/clip-vit-base-patch32"
    processor_class = AutoProcessor
    model_class = CLIPModel

    def embed_images(self, images: Sequence[str | Path | Image.Image]) -> torch.Tensor:
        self._validate_images(images)

        processor, model = self.load_model()
        pil_images = [self._to_pil_image(image) for image in images]
        inputs = processor(images=pil_images, return_tensors="pt")
        inputs = self._move_inputs_to_device(inputs)

        with torch.inference_mode():
            image_features = model.get_image_features(**inputs)

        return self._normalize_embeddings(_coerce_clip_features(image_features))

    def embed_texts(self, texts: Sequence[str]) -> torch.Tensor:
        self._validate_texts(texts)

        processor, model = self.load_model()
        inputs = processor(
            text=list(texts),
            padding=True,
            truncation=True,
            return_tensors="pt",
        )
        inputs = self._move_inputs_to_device(inputs)

        with torch.inference_mode():
            text_features = model.get_text_features(**inputs)

        return self._normalize_embeddings(_coerce_clip_features(text_features))


def _coerce_clip_features(output) -> torch.Tensor:
    if isinstance(output, torch.Tensor):
        return output

    for attr_name in ("image_embeds", "text_embeds", "pooler_output"):
        value = getattr(output, attr_name, None)
        if isinstance(value, torch.Tensor):
            return value

    last_hidden_state = getattr(output, "last_hidden_state", None)
    if isinstance(last_hidden_state, torch.Tensor):
        if last_hidden_state.ndim == 3:
            return last_hidden_state[:, 0, :]
        return last_hidden_state

    raise TypeError(
        "CLIP feature output did not match the expected contract. "
        f"Expected a tensor or an object with embeddings, got {type(output).__name__}."
    )

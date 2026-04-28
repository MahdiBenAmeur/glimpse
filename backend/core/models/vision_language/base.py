from __future__ import annotations

from pathlib import Path
from typing import Sequence
import torch
from PIL import Image
from huggingface_hub import snapshot_download
from transformers.image_utils import load_image

from backend.config import device, models_cache_dir


class BaseEmbeddingModel:
    CKPT = ""
    processor_class = None
    model_class = None
    processor_load_kwargs: dict = {}
    model_load_kwargs: dict = {}

    def __init__(self) -> None:
        self._processor = None
        self._model = None

    def _get_processor_kwargs(self, *, local_files_only: bool) -> dict:
        kwargs = {"cache_dir": models_cache_dir, **self.processor_load_kwargs}
        if local_files_only:
            kwargs["local_files_only"] = True
        return kwargs

    def _get_model_kwargs(self, *, local_files_only: bool) -> dict:
        kwargs = {"cache_dir": models_cache_dir, **self.model_load_kwargs}
        if local_files_only:
            kwargs["local_files_only"] = True
        return kwargs

    def _load_processor(self, *, local_files_only: bool):
        return self.processor_class.from_pretrained(
            self.CKPT,
            **self._get_processor_kwargs(local_files_only=local_files_only),
        )

    def _load_model(self, *, local_files_only: bool):
        return self.model_class.from_pretrained(
            self.CKPT,
            **self._get_model_kwargs(local_files_only=local_files_only),
        )

    def is_model_downloaded(self) -> bool:
        if self._processor is not None and self._model is not None:
            return True

        try:
            snapshot_download(
                repo_id=self.CKPT,
                cache_dir=models_cache_dir,
                local_files_only=True,
                **({"allow_patterns": ["*.json", "*.txt", "*.model", "*.safetensors", "*.bin", "*.py"]}),
            )
            return True
        except Exception:
            return False

    def download_model(self) -> Path:
        if self.is_model_downloaded():
            print("Model already downloaded.", flush=True)
            return Path(models_cache_dir)

        print(f"Downloading model: {self.CKPT}", flush=True)
        processor = self._load_processor(local_files_only=False)
        model = self._load_model(local_files_only=False)
        del processor
        del model
        print("Download complete.", flush=True)
        return Path(models_cache_dir)

    def load_model(self):
        if self._processor is not None and self._model is not None:
            return self._processor, self._model

        if not self.is_model_downloaded():
            self.download_model()

        self._processor = self._load_processor(local_files_only=True)
        self._model = self._load_model(local_files_only=True).to(device)
        self._model.eval()
        return self._processor, self._model

    def unload_model(self) -> None:
        self._processor = None
        self._model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _normalize_embeddings(self, embeddings: torch.Tensor) -> torch.Tensor:
        embeddings = embeddings.to(torch.float32)
        embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        return embeddings.detach().cpu()

    def _move_inputs_to_device(self, inputs):
        if hasattr(inputs, "to"):
            return inputs.to(device)
        if isinstance(inputs, dict):
            return {
                name: tensor.to(device) if isinstance(tensor, torch.Tensor) else tensor
                for name, tensor in inputs.items()
            }
        return inputs.to(device) if isinstance(inputs, torch.Tensor) else inputs

    def _to_pil_image(self, image: str | Path | Image.Image) -> Image.Image:
        if isinstance(image, Image.Image):
            return image.convert("RGB")
        return load_image(str(image)).convert("RGB")

    def _validate_images(self, images: Sequence[str | Path | Image.Image]) -> None:
        if not images:
            raise ValueError("images must not be empty")

    def _validate_texts(self, texts: Sequence[str]) -> None:
        if not texts:
            raise ValueError("texts must not be empty")
        if any(not text.strip() for text in texts):
            raise ValueError("texts must not contain empty strings")

    def embed_images(self, images: Sequence[str | Path | Image.Image]) -> torch.Tensor:
        raise NotImplementedError

    def embed_image(self, image: str | Path | Image.Image) -> torch.Tensor:
        return self.embed_images([image])[0]

    def embed_texts(self, texts: Sequence[str]) -> torch.Tensor:
        raise NotImplementedError

    def embed_text(self, text: str) -> torch.Tensor:
        return self.embed_texts([text])[0]

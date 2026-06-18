from __future__ import annotations

import shutil
from pathlib import Path
from typing import Sequence
import av
import numpy as np
import torch
from PIL import Image
from transformers.image_utils import load_image

from backend.config import DEVICE, MODELS_CACHE_DIR


class BaseEmbeddingModel:
    """Shared lifecycle and preprocessing helpers for image-text embedding models."""

    CKPT = ""
    embedding_dim: int | None = None
    processor_class = None
    model_class = None
    processor_load_kwargs: dict = {}
    model_load_kwargs: dict = {}

    def __init__(self) -> None:
        self._processor = None
        self._model = None

    def get_embedding_dim(self) -> int:
        """Return the static embedding size exposed by the concrete model wrapper."""
        if self.embedding_dim is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} must define a static embedding_dim"
            )
        return int(self.embedding_dim)

    def _get_processor_kwargs(self, *, local_files_only: bool) -> dict:
        """Build Hugging Face processor loading options for cache-aware loading."""
        kwargs = {"cache_dir": MODELS_CACHE_DIR, **self.processor_load_kwargs}
        if local_files_only:
            kwargs["local_files_only"] = True
        return kwargs

    def _get_model_kwargs(self, *, local_files_only: bool) -> dict:
        """Build Hugging Face model loading options for cache-aware loading."""
        kwargs = {"cache_dir": MODELS_CACHE_DIR, **self.model_load_kwargs}
        if local_files_only:
            kwargs["local_files_only"] = True
        return kwargs

    def _load_processor(self, *, local_files_only: bool):
        """Instantiate the configured processor from the model checkpoint."""
        return self.processor_class.from_pretrained(
            self.CKPT,
            **self._get_processor_kwargs(local_files_only=local_files_only),
        )

    def _load_model(self, *, local_files_only: bool):
        """Instantiate the configured model from the model checkpoint."""
        return self.model_class.from_pretrained(
            self.CKPT,
            **self._get_model_kwargs(local_files_only=local_files_only),
        )

    def is_model_downloaded(self) -> bool:
        """Check whether the checkpoint is available in the local Hugging Face cache."""
        if self._processor is not None and self._model is not None:
            return True

        repo_cache_dir = Path(MODELS_CACHE_DIR) / f"models--{self.CKPT.replace('/', '--')}"
        blobs_dir = repo_cache_dir / "blobs"
        if not blobs_dir.exists():
            return False

        incomplete_files = list(blobs_dir.glob("*.incomplete"))
        if incomplete_files:
            return False

        snapshots_dir = repo_cache_dir / "snapshots"
        if not snapshots_dir.exists():
            return False

        has_weight_file = any(
            list(snapshot_dir.glob("*.safetensors")) or list(snapshot_dir.glob("*.bin"))
            for snapshot_dir in snapshots_dir.iterdir()
            if snapshot_dir.is_dir()
        )
        if not has_weight_file:
            return False

        return True

    def download_model(self) -> Path:
        """Download processor and model files into the configured model cache."""
        if self.is_model_downloaded():
            print("Model already downloaded.", flush=True)
            return Path(MODELS_CACHE_DIR)

        print(f"Downloading model: {self.CKPT}", flush=True)
        processor = self._load_processor(local_files_only=False)
        model = self._load_model(local_files_only=False)
        del processor
        del model
        print("Download complete.", flush=True)
        return Path(MODELS_CACHE_DIR)

    def delete_model(self) -> Path:
        """Unload and remove this checkpoint's cached model directory."""
        repo_cache_dir = Path(MODELS_CACHE_DIR) / f"models--{self.CKPT.replace('/', '--')}"
        self.unload_model()
        if repo_cache_dir.exists():
            shutil.rmtree(repo_cache_dir)
        return repo_cache_dir

    def load_model(self):
        """Load processor and model into memory, downloading them first if needed."""
        if self._processor is not None and self._model is not None:
            return self._processor, self._model

        if not self.is_model_downloaded():
            self.download_model()

        try:
            self._processor = self._load_processor(local_files_only=True)
        except Exception:
            self._processor = self._load_processor(local_files_only=False)

        try:
            self._model = self._load_model(local_files_only=True).to(DEVICE)
        except Exception:
            self._model = self._load_model(local_files_only=False).to(DEVICE)

        self._model.eval()
        return self._processor, self._model

    def unload_model(self) -> None:
        """Release cached model objects and clear CUDA cache when available."""
        self._processor = None
        self._model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _normalize_embeddings(self, embeddings: torch.Tensor) -> torch.Tensor:
        """Return L2-normalized float32 embeddings on CPU for vector search."""
        embeddings = embeddings.to(torch.float32)
        embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        return embeddings.detach().cpu()

    def _move_inputs_to_device(self, inputs):
        """Move tensors inside processor outputs to the configured compute device."""
        if hasattr(inputs, "to"):
            return inputs.to(DEVICE)
        if isinstance(inputs, dict):
            return {
                name: tensor.to(DEVICE) if isinstance(tensor, torch.Tensor) else tensor
                for name, tensor in inputs.items()
            }
        return  inputs

    def _to_pil_image(self, image: str | Path | Image.Image) -> Image.Image:
        """Load a path-like image or normalize an existing PIL image to RGB."""
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
        """Embed a batch of images into the shared vector space."""
        raise NotImplementedError

    def embed_image(self, image: str | Path | Image.Image) -> torch.Tensor:
        return self.embed_images([image])[0]

    def embed_texts(self, texts: Sequence[str]) -> torch.Tensor:
        """Embed a batch of text queries into the shared vector space."""
        raise NotImplementedError

    def embed_text(self, text: str) -> torch.Tensor:
        return self.embed_texts([text])[0]

    def _detect_video_scenes(self, video_path: str | Path) -> list[tuple]:
        from scenedetect import ContentDetector, detect

        return detect(str(video_path), ContentDetector(), start_in_scene=True)

    def _get_keyframes_from_video(
        self, video_path: str | Path, scenes: list[tuple],
    ) -> list[Image.Image]:
        keyframes: list[Image.Image] = []
        container = av.open(str(video_path))
        stream = container.streams.video[0]
        for start, end in scenes:
            middle = (start.get_seconds() + end.get_seconds()) / 2.0
            ts = int(middle / float(stream.time_base))
            container.seek(ts, stream=stream)
            for frame in container.decode(video=0):
                keyframes.append(Image.fromarray(frame.to_ndarray(format="rgb24")))
                break
        container.close()
        return keyframes

    def embed_video_keyframes(
        self,
        video_paths: Sequence[str | Path],
    ) -> dict:
        self._validate_images(video_paths)
        all_keyframes: list[Image.Image] = []
        mapping: list[dict] = []
        for video_path in video_paths:
            scenes = self._detect_video_scenes(video_path)
            kf = self._get_keyframes_from_video(video_path, scenes)
            if not kf:
                kf = [self._to_pil_image(video_path)]
            info = {
                "video_path": str(video_path),
                "keyframe_start": len(all_keyframes),
                "keyframe_count": len(kf),
            }
            all_keyframes.extend(kf)
            mapping.append(info)
        if not all_keyframes:
            raise ValueError("No keyframes extracted from any video")
        embeddings = self.embed_images(all_keyframes)
        return {"embeddings": embeddings, "mapping": mapping}

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import av
import numpy as np
import torch
from huggingface_hub import snapshot_download
from PIL import Image
from transformers import XCLIPProcessor, XCLIPModel

from backend.config import DEVICE, MODELS_CACHE_DIR
from backend.core.models.vision_language.base import BaseEmbeddingModel


class XClipVideoEmbeddingModel(BaseEmbeddingModel):
    CKPT = "microsoft/xclip-base-patch32"
    embedding_dim = 512
    NUM_FRAMES = 8

    def __init__(self) -> None:
        super().__init__()
        self._processor = None

    def is_model_downloaded(self) -> bool:
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

    def _load_processor(self, *, local_files_only: bool):
        return XCLIPProcessor.from_pretrained(
            self.CKPT,
            cache_dir=MODELS_CACHE_DIR,
            **({"local_files_only": True} if local_files_only else {}),
        )

    def _load_model(self, *, local_files_only: bool):
        return XCLIPModel.from_pretrained(
            self.CKPT,
            cache_dir=MODELS_CACHE_DIR,
            **({"local_files_only": True} if local_files_only else {}),
        )

    def load_model(self):
        if self._processor is not None and self._model is not None:
            return self._processor, self._model

        if not self.is_model_downloaded():
            self.download_model()

        self._processor = self._load_processor(local_files_only=True)
        self._model = self._load_model(local_files_only=True).to(DEVICE)
        self._model.eval()
        return self._processor, self._model

    def get_embedding_dim(self) -> int:
        return self.embedding_dim

    @staticmethod
    def _sample_frame_indices(num_frames: int, total_frames: int) -> list[int]:
        if total_frames <= num_frames:
            return list(range(total_frames))
        indices = np.linspace(0, total_frames - 1, num=num_frames, dtype=np.int64)
        return indices.tolist()

    @staticmethod
    def _read_video_frames(video_path: str | Path) -> np.ndarray:
        container = av.open(str(video_path))
        stream = container.streams.video[0]
        total_frames = stream.frames
        if total_frames == 0:
            total_frames = int(float(stream.duration * stream.time_base) * float(stream.average_rate)) if stream.duration is not None else 300

        indices = set(XClipVideoEmbeddingModel._sample_frame_indices(XClipVideoEmbeddingModel.NUM_FRAMES, total_frames))

        frames: list[np.ndarray] = []
        container.seek(0)
        for i, frame in enumerate(container.decode(video=0)):
            if i in indices:
                frames.append(frame.to_ndarray(format="rgb24"))
            if len(frames) >= XClipVideoEmbeddingModel.NUM_FRAMES:
                break
        container.close()

        if not frames:
            raise ValueError(f"No frames extracted from video: {video_path}")
        return np.stack(frames)

    def embed_videos(self, video_paths: Sequence[str | Path]) -> torch.Tensor:
        processor, model = self.load_model()
        all_embeddings: list[torch.Tensor] = []
        for video_path in video_paths:
            frames = self._read_video_frames(video_path)
            inputs = processor.image_processor(
                images=list(frames),
                return_tensors="pt",
            )
            inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
            # image_processor returns (num_frames, C, H, W);
            # get_video_features expects (1, num_frames, C, H, W)
            if inputs["pixel_values"].dim() == 4:
                inputs["pixel_values"] = inputs["pixel_values"].unsqueeze(0)
            with torch.inference_mode():
                outputs = model.get_video_features(**inputs)
            video_embed = outputs.pooler_output
            all_embeddings.append(video_embed)

        embeddings = torch.cat(all_embeddings, dim=0)
        return self._normalize_embeddings(embeddings)

    def embed_video(self, video_path: str | Path) -> torch.Tensor:
        return self.embed_videos([video_path])[0]

    def embed_texts(self, texts: Sequence[str]) -> torch.Tensor:
        self._validate_texts(texts)
        processor, model = self.load_model()

        inputs = processor(
            text=list(texts),
            return_tensors="pt",
            padding=True,
        )
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        with torch.inference_mode():
            text_features = model.get_text_features(**inputs)

        text_features = text_features.pooler_output
        return self._normalize_embeddings(text_features)

    def embed_images(self, images: Sequence[str | Path | Image.Image]) -> torch.Tensor:
        raise NotImplementedError("XCLIPVideoEmbeddingModel does not support image embedding. Use CLIP or SigLIP models for images")

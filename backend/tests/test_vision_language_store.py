import json
import tempfile
import unittest
from pathlib import Path

import faiss

from backend.core.models.vision_language import store as image_store
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.video import store as video_store
from backend.services import library_state_service
from backend.utils.vector_store_utils import create_empty_index


class _FakeEmbeddingModel(BaseEmbeddingModel):
    CKPT = "fake/model"

    def __init__(self, embedding_dim: int = 384) -> None:
        super().__init__()
        self.embedding_dim = embedding_dim


def _scoped_path(root: Path, model_id: str, store_type: str = "unified") -> Path:
    return root / "vector_stores" / model_id / store_type


class VisionLanguageStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.model = _FakeEmbeddingModel(embedding_dim=384)

        self._previous_image_state = (
            image_store.image_vs,
            image_store.image_vs_meta_data,
            image_store.IMAGE_VS_PATH,
            image_store.model_scoped_vs_path,
        )
        self._previous_video_state = (
            video_store.video_vs,
            video_store.video_vs_meta_data,
            video_store.VIDEO_VS_PATH,
            video_store.model_scoped_vs_path,
        )
        self._previous_library_state = (
            library_state_service.IMAGE_META_PATH,
            library_state_service.model_scoped_vs_path,
        )

        image_store.reset_image_vector_store()
        video_store.reset_video_vector_store()
        image_store.IMAGE_VS_PATH = self.root / "legacy_image_store"
        video_store.VIDEO_VS_PATH = self.root / "legacy_video_store"
        library_state_service.IMAGE_META_PATH = (
            image_store.IMAGE_VS_PATH / "meta_data.json"
        )
        image_store.model_scoped_vs_path = lambda model_id, store_type="unified": (
            _scoped_path(self.root, model_id, store_type)
        )
        video_store.model_scoped_vs_path = lambda model_id, store_type="unified": (
            _scoped_path(self.root, model_id, store_type)
        )
        library_state_service.model_scoped_vs_path = (
            lambda model_id, store_type="unified": _scoped_path(
                self.root, model_id, store_type
            )
        )

    def tearDown(self) -> None:
        (
            image_store.image_vs,
            image_store.image_vs_meta_data,
            image_store.IMAGE_VS_PATH,
            image_store.model_scoped_vs_path,
        ) = self._previous_image_state
        (
            video_store.video_vs,
            video_store.video_vs_meta_data,
            video_store.VIDEO_VS_PATH,
            video_store.model_scoped_vs_path,
        ) = self._previous_video_state
        (
            library_state_service.IMAGE_META_PATH,
            library_state_service.model_scoped_vs_path,
        ) = self._previous_library_state
        self.tmp.cleanup()

    def test_image_store_initializes_empty_model_scoped_directory(self):
        store_dir = _scoped_path(self.root, "clip-vit-b32", "image")
        store_dir.mkdir(parents=True)

        vs, meta = image_store.load_image_vector_store(self.model, "clip-vit-b32")

        self.assertEqual(vs.ntotal, 0)
        self.assertEqual(meta["_embedding_dim"], 384)
        self.assertEqual(meta["_model_ckpt"], "fake/model")
        self.assertEqual(meta["_model_id"], "clip-vit-b32")
        self.assertTrue((store_dir / "index.faiss").exists())
        self.assertTrue((store_dir / "meta_data.json").exists())

    def test_image_store_migrates_saved_metadata_missing_embedding_dim(self):
        store_dir = image_store.IMAGE_VS_PATH
        store_dir.mkdir(parents=True)
        faiss.write_index(create_empty_index(384), str(store_dir / "index.faiss"))
        with (store_dir / "meta_data.json").open("w", encoding="utf-8") as handle:
            json.dump({"_next_id": 0}, handle)

        _, meta = image_store.load_image_vector_store(self.model)

        self.assertEqual(meta["_embedding_dim"], 384)
        self.assertEqual(meta["_model_ckpt"], "fake/model")
        with (store_dir / "meta_data.json").open("r", encoding="utf-8") as handle:
            saved_meta = json.load(handle)
        self.assertEqual(saved_meta["_embedding_dim"], 384)
        self.assertEqual(saved_meta["_model_ckpt"], "fake/model")

    def test_model_aware_metadata_loader_reads_scoped_image_store(self):
        store_dir = _scoped_path(self.root, "clip-vit-b32", "image")
        store_dir.mkdir(parents=True)
        with (store_dir / "meta_data.json").open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "_next_id": 1,
                    "_embedding_dim": 384,
                    "_model_ckpt": "fake/model",
                    "_model_id": "clip-vit-b32",
                    "0": {"image_path": "/tmp/example.jpg"},
                },
                handle,
            )

        meta = library_state_service.load_image_vs_meta_data("clip-vit-b32")

        self.assertEqual(meta["0"]["image_path"], "/tmp/example.jpg")
        self.assertEqual(meta["_model_id"], "clip-vit-b32")

    def test_video_store_initializes_empty_model_scoped_directory(self):
        store_dir = _scoped_path(self.root, "clip-vit-b32", "video")
        store_dir.mkdir(parents=True)

        vs, meta = video_store.load_video_vector_store(self.model, "clip-vit-b32")

        self.assertEqual(vs.ntotal, 0)
        self.assertEqual(meta["_embedding_dim"], 384)
        self.assertEqual(meta["_model_ckpt"], "fake/model")
        self.assertEqual(meta["_model_id"], "clip-vit-b32")
        self.assertTrue((store_dir / "index.faiss").exists())
        self.assertTrue((store_dir / "meta_data.json").exists())


if __name__ == "__main__":
    unittest.main()

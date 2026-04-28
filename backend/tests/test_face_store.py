import unittest
from pathlib import Path

import numpy as np
import torch

from backend.core.models.faces import store
from backend.utils.vector_store_utils import embedding_row


class _FakeCoords:
    def __init__(self, box: list[float]) -> None:
        self._box = box

    def tolist(self) -> list[float]:
        return list(self._box)


class _FakeBox:
    def __init__(self, box: list[float]) -> None:
        self.xyxy = [_FakeCoords(box)]


def _vector(*values: float) -> torch.Tensor:
    raw = torch.zeros(store.face_emb_dim, dtype=torch.float32)
    raw[: len(values)] = torch.tensor(values, dtype=torch.float32)
    return store._normalize_embedding(raw)


class FaceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous_state = (
            store.face_vs,
            store.face_meta_data,
            store.person_vs,
            store.person_meta_data,
        )
        store.face_vs = store._empty_index()
        store.face_meta_data = {"_next_id": 0}
        store.person_vs = store._empty_index()
        store.person_meta_data = {"_next_id": 0}

    def tearDown(self) -> None:
        (
            store.face_vs,
            store.face_meta_data,
            store.person_vs,
            store.person_meta_data,
        ) = self._previous_state

    def _add_face(
        self,
        embedding: torch.Tensor,
        *,
        image_path: str,
        person_id: int | None = None,
        box: list[float] | None = None,
    ) -> dict:
        face_id = int(store.face_meta_data["_next_id"])
        store.face_meta_data["_next_id"] = face_id + 1
        face_box = box or [0.0, 0.0, 128.0, 128.0]
        quality_score = store._face_quality_weight(face_box)
        store.face_vs.add_with_ids(embedding_row(embedding), np.array([face_id], dtype=np.int64))
        store.face_meta_data[str(face_id)] = {
            "person_id": person_id,
            "image_path": image_path,
            "created_at": None,
            "face_box": face_box,
            "quality_score": quality_score,
            "detection_confidence": 1.0,
        }
        return {
            "face_id": face_id,
            "image_path": image_path,
            "embedding": embedding,
            "face_box": face_box,
            "created_at": None,
            "quality_score": quality_score,
            "detection_confidence": 1.0,
        }

    def _seed_person(self, person_id: int, embeddings: list[torch.Tensor], *, prefix: str) -> None:
        samples = [
            self._add_face(embedding, image_path=f"{prefix}-{index}.jpg", person_id=person_id)
            for index, embedding in enumerate(embeddings)
        ]
        entry = store._new_person_entry(samples[0])
        for sample in samples[1:]:
            store._add_sample_to_person_entry(entry, sample)
        store.person_meta_data[str(person_id)] = entry
        store.person_meta_data["_next_id"] = max(int(store.person_meta_data["_next_id"]), person_id + 1)

    def test_add_faces_to_vector_store_stores_unassigned_embeddings_only(self):
        stats = store.add_faces_to_vector_store(
            {
                Path("self-a.jpg"): torch.stack([_vector(1.0, 0.0, 0.0), _vector(0.9, 0.1, 0.0)]),
                Path("other.jpg"): torch.stack([_vector(-1.0, 0.0, 0.0)]),
            },
            {
                Path("self-a.jpg"): [_FakeBox([0, 0, 64, 64]), _FakeBox([0, 0, 256, 256])],
                Path("other.jpg"): [_FakeBox([0, 0, 64, 64])],
            },
        )

        self.assertEqual(stats["indexed_face_count"], 3)
        self.assertEqual(stats["person_store_total"], 0)
        self.assertEqual(store.face_vs.ntotal, 3)
        self.assertEqual(store.person_vs.ntotal, 0)
        self.assertTrue(
            all(
                entry.get("person_id") is None
                for key, entry in store.face_meta_data.items()
                if not str(key).startswith("_")
            )
        )

    def test_finalize_face_clusters_assigns_people_after_all_faces_are_embedded(self):
        for index, embedding in enumerate([
            _vector(1.0, 0.0, 0.0),
            _vector(0.99, 0.08, 0.0),
            _vector(0.98, 0.12, 0.0),
            _vector(-1.0, 0.0, 0.0),
            _vector(-0.99, 0.08, 0.0),
        ]):
            self._add_face(embedding, image_path=f"face-{index}.jpg")

        stats = store.finalize_face_clusters()

        person_ids = sorted(int(key) for key in store.person_meta_data.keys() if not str(key).startswith("_"))
        face_person_ids = {
            int(entry["person_id"])
            for key, entry in store.face_meta_data.items()
            if not str(key).startswith("_")
        }

        self.assertEqual(stats["assigned_face_count"], 5)
        self.assertEqual(len(person_ids), 2)
        self.assertEqual(len(face_person_ids), 2)

    def test_quality_pipeline_low_quality_face_joins_only_with_enough_clear_matches(self):
        previous_settings = (
            store.FACE_PIPELINE_HIGH_QUALITY_PERCENTAGE,
            store.FACE_PIPELINE_LOW_MIN_MATCHES,
        )
        try:
            store.FACE_PIPELINE_HIGH_QUALITY_PERCENTAGE = 0.75
            store.FACE_PIPELINE_LOW_MIN_MATCHES = 3

            for index, embedding in enumerate([
                _vector(1.0, 0.0, 0.0),
                _vector(0.99, 0.08, 0.0),
                _vector(0.98, 0.12, 0.0),
            ]):
                self._add_face(
                    embedding,
                    image_path=f"high-{index}.jpg",
                    box=[0.0, 0.0, 256.0 - index, 256.0 - index],
                )
            self._add_face(
                _vector(0.97, 0.16, 0.0),
                image_path="low-clear.jpg",
                box=[0.0, 0.0, 64.0, 64.0],
            )

            stats = store.finalize_face_clusters()

            person_ids = [int(key) for key in store.person_meta_data.keys() if not str(key).startswith("_")]
            assigned_face_count = sum(
                1
                for key, entry in store.face_meta_data.items()
                if not str(key).startswith("_") and entry.get("person_id") is not None
            )

            self.assertEqual(len(person_ids), 1)
            self.assertEqual(assigned_face_count, 4)
            self.assertEqual(stats["low_quality_joined_person_count"], 1)
            self.assertEqual(stats["unknown_face_count"], 0)
        finally:
            (
                store.FACE_PIPELINE_HIGH_QUALITY_PERCENTAGE,
                store.FACE_PIPELINE_LOW_MIN_MATCHES,
            ) = previous_settings

    def test_quality_pipeline_low_quality_faces_do_not_create_people(self):
        previous_settings = (
            store.FACE_PIPELINE_HIGH_QUALITY_PERCENTAGE,
            store.FACE_PIPELINE_LOW_MIN_MATCHES,
        )
        try:
            store.FACE_PIPELINE_HIGH_QUALITY_PERCENTAGE = 0.5
            store.FACE_PIPELINE_LOW_MIN_MATCHES = 3

            self._add_face(_vector(1.0, 0.0, 0.0), image_path="high-a.jpg", box=[0.0, 0.0, 256.0, 256.0])
            self._add_face(_vector(0.99, 0.08, 0.0), image_path="high-b.jpg", box=[0.0, 0.0, 240.0, 240.0])
            self._add_face(_vector(0.98, 0.12, 0.0), image_path="low-same.jpg", box=[0.0, 0.0, 64.0, 64.0])
            self._add_face(_vector(-1.0, 0.0, 0.0), image_path="low-other.jpg", box=[0.0, 0.0, 60.0, 60.0])

            stats = store.finalize_face_clusters()

            person_ids = [int(key) for key in store.person_meta_data.keys() if not str(key).startswith("_")]
            unknown_paths = {
                entry["image_path"]
                for key, entry in store.face_meta_data.items()
                if not str(key).startswith("_") and entry.get("person_id") is None
            }

            self.assertEqual(len(person_ids), 1)
            self.assertEqual(stats["unknown_face_count"], 2)
            self.assertEqual(unknown_paths, {"low-same.jpg", "low-other.jpg"})
        finally:
            (
                store.FACE_PIPELINE_HIGH_QUALITY_PERCENTAGE,
                store.FACE_PIPELINE_LOW_MIN_MATCHES,
            ) = previous_settings


if __name__ == "__main__":
    unittest.main()

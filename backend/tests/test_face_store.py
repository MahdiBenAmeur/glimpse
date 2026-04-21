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


def _make_cluster(samples: list[dict]) -> dict:
    cluster = store._new_batch_cluster(samples[0])
    for sample in samples[1:]:
        store._add_sample_to_cluster(cluster, sample)
    return cluster


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

    def _seed_person(self, person_id: int, embeddings: list[torch.Tensor], *, prefix: str) -> None:
        samples = []
        for index, embedding in enumerate(embeddings):
            sample = {
                "image_path": f"{prefix}-{index}.jpg",
                "embedding": embedding,
                "face_box": [0.0, 0.0, 128.0, 128.0],
                "created_at": None,
                "quality_score": store._face_quality_weight([0.0, 0.0, 128.0, 128.0]),
            }
            samples.append(sample)

            face_id = int(store.face_meta_data["_next_id"])
            store.face_meta_data["_next_id"] = face_id + 1
            store.face_vs.add_with_ids(
                embedding_row(embedding),
                np.array([face_id], dtype=np.int64),
            )
            store.face_meta_data[str(face_id)] = {
                "person_id": person_id,
                "image_path": sample["image_path"],
                "created_at": sample["created_at"],
                "face_box": sample["face_box"],
                "quality_score": sample["quality_score"],
            }

        cluster = _make_cluster(samples)
        store.person_meta_data[str(person_id)] = store._person_entry_from_cluster(cluster)
        store.person_vs.add_with_ids(
            embedding_row(cluster["centroid"]),
            np.array([person_id], dtype=np.int64),
        )
        next_person_id = int(store.person_meta_data["_next_id"])
        store.person_meta_data["_next_id"] = max(next_person_id, person_id + 1)

    def test_add_faces_to_vector_store_clusters_batch_and_weights_centroid(self):
        low_quality_face = _vector(1.0, 0.0, 0.0)
        high_quality_face = _vector(0.8, 0.6, 0.0)
        different_person_face = _vector(-1.0, 0.0, 0.0)

        stats = store.add_faces_to_vector_store(
            {
                Path("self-a.jpg"): torch.stack([low_quality_face, high_quality_face]),
                Path("other.jpg"): torch.stack([different_person_face]),
            },
            {
                Path("self-a.jpg"): [_FakeBox([0, 0, 64, 64]), _FakeBox([0, 0, 256, 256])],
                Path("other.jpg"): [_FakeBox([0, 0, 64, 64])],
            },
        )

        self.assertEqual(stats["indexed_face_count"], 3)
        self.assertEqual(stats["person_store_total"], 2)
        self.assertEqual(stats["batch_cluster_count"], 2)

        merged_person = next(
            entry
            for key, entry in store.person_meta_data.items()
            if not str(key).startswith("_") and entry.get("count") == 2
        )
        centroid = torch.tensor(merged_person["centroid"], dtype=torch.float32)
        self.assertGreater(float(torch.dot(centroid, high_quality_face)), float(torch.dot(centroid, low_quality_face)))

    def test_rank_person_candidates_prefers_face_votes(self):
        self._seed_person(0, [_vector(1.0, 0.0, 0.0), _vector(0.95, 0.31, 0.0)], prefix="self")
        self._seed_person(1, [_vector(0.82, 0.57, 0.0)], prefix="other")

        ranked_candidates = store._rank_person_candidates(_vector(0.98, 0.2, 0.0))

        self.assertTrue(ranked_candidates)
        self.assertEqual(ranked_candidates[0]["person_id"], 0)
        self.assertGreaterEqual(ranked_candidates[0]["face_hits"], 2)

    def test_merge_duplicate_people_updates_face_assignments(self):
        self._seed_person(0, [_vector(1.0, 0.0, 0.0), _vector(0.99, 0.1, 0.0)], prefix="self-main")
        self._seed_person(1, [_vector(0.98, 0.18, 0.0), _vector(0.97, 0.22, 0.0)], prefix="self-dup")

        merge_stats = store._merge_duplicate_people(store.face_meta_data, store.person_meta_data)

        person_ids = [int(key) for key in store.person_meta_data.keys() if not str(key).startswith("_")]
        face_person_ids = {
            int(entry["person_id"])
            for key, entry in store.face_meta_data.items()
            if not str(key).startswith("_")
        }

        self.assertEqual(merge_stats["merged_person_count"], 1)
        self.assertEqual(len(person_ids), 1)
        self.assertEqual(len(face_person_ids), 1)

    def test_finalize_face_clusters_uses_centroid_and_top_faces(self):
        self._seed_person(
            0,
            [_vector(1.0, 0.0, 0.0), _vector(0.98, 0.2, 0.0), _vector(0.95, 0.27, 0.0)],
            prefix="self-clear",
        )
        self._seed_person(
            1,
            [_vector(0.97, 0.24, 0.0), _vector(0.96, 0.28, 0.0), _vector(0.94, 0.33, 0.0)],
            prefix="self-duplicate",
        )
        self._seed_person(
            2,
            [_vector(-1.0, 0.0, 0.0), _vector(-0.98, 0.18, 0.0)],
            prefix="other-person",
        )

        merge_stats = store.finalize_face_clusters()

        person_ids = sorted(int(key) for key in store.person_meta_data.keys() if not str(key).startswith("_"))
        face_person_ids = {
            int(entry["person_id"])
            for key, entry in store.face_meta_data.items()
            if not str(key).startswith("_")
        }

        self.assertEqual(merge_stats["merged_person_count"], 1)
        self.assertEqual(person_ids, [0, 2])
        self.assertEqual(face_person_ids, {0, 2})


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
import threading
from typing import Any

import faiss
import numpy as np
import torch

from backend.config import (
    FACE_ASSIGNMENT_TOP_K,
    FACE_BATCH_CLUSTER_THRESHOLD,
    FACE_FINAL_MERGE_AVG_EXEMPLAR_THRESHOLD,
    FACE_FINAL_MERGE_CENTROID_THRESHOLD,
    FACE_FINAL_MERGE_EXEMPLAR_THRESHOLD,
    FACE_MERGE_THRESHOLD,
    FACE_POST_MERGE_THRESHOLD,
    FACE_QUALITY_REFERENCE_PIXELS,
    FACE_STRONG_MATCH_THRESHOLD,
    FACE_TOP_EXEMPLAR_COUNT,
    FACE_VS_PATH,
    PERSON_VS_PATH,
)
from backend.utils.vector_store_utils import consume_next_id, embedding_row, load_or_init_vector_store, save_vs


face_emb_dim = 512
face_vs = None
face_meta_data = None
person_vs = None
person_meta_data = None


def _log_face_store(message: str, **fields: Any) -> None:
    timestamp = datetime.utcnow().isoformat(timespec="seconds")
    thread = threading.current_thread()
    payload = {
        "thread_name": thread.name,
        "thread_ident": thread.ident,
        **fields,
    }
    suffix = ""
    if payload:
        suffix = " | " + ", ".join(f"{key}={value!r}" for key, value in payload.items())
    print(f"[{timestamp}] [FACE STORE] {message}{suffix}", flush=True)


def reset_face_vector_stores() -> None:
    global face_vs
    global face_meta_data
    global person_vs
    global person_meta_data
    _log_face_store(
        "Resetting cached face stores",
        had_face_vs=face_vs is not None,
        had_face_meta_data=face_meta_data is not None,
        had_person_vs=person_vs is not None,
        had_person_meta_data=person_meta_data is not None,
        face_vs_id=id(face_vs) if face_vs is not None else None,
        person_vs_id=id(person_vs) if person_vs is not None else None,
    )
    face_vs = None
    face_meta_data = None
    person_vs = None
    person_meta_data = None


def load_face_vector_store():
    global face_vs
    global face_meta_data
    if face_vs is not None and face_meta_data is not None:
        _log_face_store(
            "Returning cached face vector store",
            ntotal=int(face_vs.ntotal),
            metadata_entry_count=len(face_meta_data),
            face_vs_id=id(face_vs),
        )
        return face_vs, face_meta_data

    _log_face_store("Loading face vector store from disk")
    face_vs, face_meta_data = load_or_init_vector_store(FACE_VS_PATH, emb_dim=face_emb_dim)
    _log_face_store(
        "Loaded face vector store from disk",
        ntotal=int(face_vs.ntotal),
        metadata_entry_count=len(face_meta_data),
        face_vs_id=id(face_vs),
    )
    return face_vs, face_meta_data


def load_person_vector_store():
    global person_vs
    global person_meta_data
    if person_vs is not None and person_meta_data is not None:
        _log_face_store(
            "Returning cached person vector store",
            ntotal=int(person_vs.ntotal),
            metadata_entry_count=len(person_meta_data),
            person_vs_id=id(person_vs),
        )
        return person_vs, person_meta_data

    _log_face_store("Loading person vector store from disk")
    person_vs, person_meta_data = load_or_init_vector_store(PERSON_VS_PATH, emb_dim=face_emb_dim)
    _log_face_store(
        "Loaded person vector store from disk",
        ntotal=int(person_vs.ntotal),
        metadata_entry_count=len(person_meta_data),
        person_vs_id=id(person_vs),
    )
    return person_vs, person_meta_data


def save_face_vector_stores() -> None:
    face_vector_store, face_store_meta_data = load_face_vector_store()
    person_vector_store, person_store_meta_data = load_person_vector_store()
    _log_face_store(
        "Saving face and person vector stores",
        face_ntotal=int(face_vector_store.ntotal),
        face_metadata_entry_count=len(face_store_meta_data),
        person_ntotal=int(person_vector_store.ntotal),
        person_metadata_entry_count=len(person_store_meta_data),
    )
    save_vs(face_vector_store, face_store_meta_data, FACE_VS_PATH)
    save_vs(person_vector_store, person_store_meta_data, PERSON_VS_PATH)
    _log_face_store("Saved face and person vector stores")


def _normalize_embedding(embedding: torch.Tensor) -> torch.Tensor:
    vector = embedding.detach().cpu().to(torch.float32).reshape(-1)
    norm = vector.norm().clamp_min(1e-12)
    return vector / norm


def _empty_index() -> faiss.IndexIDMap2:
    return faiss.IndexIDMap2(faiss.IndexFlatIP(face_emb_dim))


def _face_box_area(face_box: list[float]) -> float:
    left, top, right, bottom = [float(value) for value in face_box]
    return max(right - left, 1.0) * max(bottom - top, 1.0)


def _face_quality_weight(face_box: list[float]) -> float:
    area = _face_box_area(face_box)
    return max(1.0, math.sqrt(area / FACE_QUALITY_REFERENCE_PIXELS))


def _make_face_sample(
    *,
    image_path: Path,
    embedding: torch.Tensor,
    face_box: list[float],
    created_at: str | None,
) -> dict[str, Any]:
    return {
        "image_path": str(image_path),
        "embedding": _normalize_embedding(embedding),
        "face_box": [float(value) for value in face_box],
        "created_at": created_at,
        "quality_score": _face_quality_weight(face_box),
    }


def _make_top_face_entry(sample: dict[str, Any]) -> dict[str, Any]:
    return {
        "embedding": sample["embedding"].tolist(),
        "quality_score": float(sample["quality_score"]),
        "image_path": sample["image_path"],
        "face_box": list(sample["face_box"]),
        "created_at": sample["created_at"],
    }


def _normalize_top_face_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None

    embedding = entry.get("embedding")
    if not isinstance(embedding, list) or len(embedding) != face_emb_dim:
        return None

    return {
        "embedding": _normalize_embedding(torch.tensor(embedding, dtype=torch.float32)).tolist(),
        "quality_score": float(entry.get("quality_score", 1.0)),
        "image_path": str(entry.get("image_path", "")),
        "face_box": [float(value) for value in entry.get("face_box", [])],
        "created_at": entry.get("created_at"),
    }


def _trim_top_faces(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_entries = []
    seen: set[tuple[str, tuple[float, ...]]] = set()

    for entry in entries:
        normalized_entry = _normalize_top_face_entry(entry)
        if normalized_entry is None:
            continue

        dedupe_key = (
            normalized_entry.get("image_path", ""),
            tuple(round(float(value), 4) for value in normalized_entry.get("face_box", [])),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized_entries.append(normalized_entry)

    normalized_entries.sort(key=lambda entry: float(entry["quality_score"]), reverse=True)
    return normalized_entries[:FACE_TOP_EXEMPLAR_COUNT]


def _top_face_entries_from_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _trim_top_faces([_make_top_face_entry(sample) for sample in samples])


def _top_face_embeddings(entry: dict[str, Any]) -> list[torch.Tensor]:
    top_faces = entry.get("_top_faces", [])
    embeddings = []
    if isinstance(top_faces, list):
        for top_face in top_faces:
            normalized_entry = _normalize_top_face_entry(top_face)
            if normalized_entry is None:
                continue
            embeddings.append(torch.tensor(normalized_entry["embedding"], dtype=torch.float32))

    if embeddings:
        return embeddings

    return [torch.tensor(entry["centroid"], dtype=torch.float32)]


def _flatten_face_samples(
    path_2_embeddings: dict[Path, torch.Tensor],
    path_2_boxes: dict[Path, list],
    *,
    path_2_created_at: dict[Path, str | None] | None,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for image_path, embeddings in path_2_embeddings.items():
        boxes = path_2_boxes.get(image_path, [])
        created_at = path_2_created_at.get(image_path) if path_2_created_at is not None else None
        for index, embedding in enumerate(embeddings):
            if index >= len(boxes):
                continue
            samples.append(
                _make_face_sample(
                    image_path=image_path,
                    embedding=embedding,
                    face_box=boxes[index].xyxy[0].tolist(),
                    created_at=created_at,
                )
            )
    return samples


def _new_batch_cluster(sample: dict[str, Any]) -> dict[str, Any]:
    embedding_sum = sample["embedding"] * float(sample["quality_score"])
    return {
        "samples": [sample],
        "embedding_sum": embedding_sum.clone(),
        "total_weight": float(sample["quality_score"]),
        "centroid": _normalize_embedding(embedding_sum),
    }


def _add_sample_to_cluster(cluster: dict[str, Any], sample: dict[str, Any]) -> None:
    cluster["samples"].append(sample)
    cluster["embedding_sum"] = cluster["embedding_sum"] + (sample["embedding"] * float(sample["quality_score"]))
    cluster["total_weight"] = float(cluster["total_weight"]) + float(sample["quality_score"])
    cluster["centroid"] = _normalize_embedding(cluster["embedding_sum"])


def _cluster_face_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not samples:
        return []

    ordered_samples = sorted(
        samples,
        key=lambda sample: (-float(sample["quality_score"]), sample["image_path"], str(sample["face_box"])),
    )
    clusters: list[dict[str, Any]] = []

    for sample in ordered_samples:
        best_cluster = None
        best_score = float("-inf")
        for cluster in clusters:
            score = float(torch.dot(sample["embedding"], cluster["centroid"]))
            if score > best_score:
                best_score = score
                best_cluster = cluster

        if best_cluster is None or best_score < FACE_BATCH_CLUSTER_THRESHOLD:
            clusters.append(_new_batch_cluster(sample))
            continue

        _add_sample_to_cluster(best_cluster, sample)

    return clusters


def _ensure_person_state(entry: dict[str, Any]) -> dict[str, Any]:
    centroid = _normalize_embedding(torch.tensor(entry.get("centroid", []), dtype=torch.float32))
    image_paths = list(entry.get("image_paths", []))
    face_boxes = list(entry.get("face_boxes", []))
    count = max(int(entry.get("count", 0)), len(image_paths), len(face_boxes), 1)

    total_weight = float(entry.get("_total_weight", max(count, 1)))
    embedding_sum_raw = entry.get("_embedding_sum")
    if not isinstance(embedding_sum_raw, list) or len(embedding_sum_raw) != face_emb_dim:
        embedding_sum = centroid * max(total_weight, 1.0)
    else:
        embedding_sum = torch.tensor(embedding_sum_raw, dtype=torch.float32)
    entry["_embedding_sum"] = embedding_sum.tolist()
    entry["_total_weight"] = max(total_weight, 1.0)

    quality_scores = list(entry.get("quality_scores", []))
    target_len = max(len(image_paths), len(face_boxes), count)
    if len(quality_scores) < target_len:
        derived_scores = quality_scores[:]
        for index in range(len(derived_scores), target_len):
            if index < len(face_boxes):
                derived_scores.append(_face_quality_weight(face_boxes[index]))
            else:
                derived_scores.append(1.0)
        quality_scores = derived_scores
    entry["quality_scores"] = quality_scores[:target_len]
    entry["centroid"] = centroid.tolist()
    entry["count"] = target_len
    if not isinstance(entry.get("_top_faces"), list):
        entry["_top_faces"] = []
    entry["_top_faces"] = _trim_top_faces(entry["_top_faces"])
    if not entry["_top_faces"]:
        entry["_top_faces"] = [
            {
                "embedding": centroid.tolist(),
                "quality_score": max(quality_scores) if quality_scores else 1.0,
                "image_path": image_paths[0] if image_paths else "",
                "face_box": list(face_boxes[0]) if face_boxes else [],
                "created_at": entry.get("image_created_ats", [None])[0] if entry.get("image_created_ats") else None,
            }
        ]
    return entry


def _person_entry_from_cluster(cluster: dict[str, Any]) -> dict[str, Any]:
    samples = cluster["samples"]
    return {
        "count": len(samples),
        "centroid": cluster["centroid"].tolist(),
        "image_paths": [sample["image_path"] for sample in samples],
        "image_created_ats": [sample["created_at"] for sample in samples],
        "face_boxes": [sample["face_box"] for sample in samples],
        "quality_scores": [float(sample["quality_score"]) for sample in samples],
        "_embedding_sum": cluster["embedding_sum"].tolist(),
        "_total_weight": float(cluster["total_weight"]),
        "_top_faces": _top_face_entries_from_samples(samples),
    }


def _rebuild_person_index(person_meta_data: dict[str, Any]):
    global person_vs

    rebuilt_index = _empty_index()
    for key in sorted((item for item in person_meta_data.keys() if not str(item).startswith("_")), key=int):
        entry = person_meta_data.get(str(key))
        if not isinstance(entry, dict):
            continue
        _ensure_person_state(entry)
        person_id = int(key)
        rebuilt_index.add_with_ids(embedding_row(torch.tensor(entry["centroid"], dtype=torch.float32)), np.array([person_id], dtype=np.int64))

    person_vs = rebuilt_index
    return rebuilt_index


def _merge_cluster_into_person(person_id: int, cluster: dict[str, Any], person_meta_data: dict[str, Any], person_vs) -> None:
    person_key = str(person_id)
    person_entry = _ensure_person_state(person_meta_data[person_key])

    updated_sum = torch.tensor(person_entry["_embedding_sum"], dtype=torch.float32) + cluster["embedding_sum"]
    updated_weight = float(person_entry["_total_weight"]) + float(cluster["total_weight"])
    updated_centroid = _normalize_embedding(updated_sum)

    person_entry["_embedding_sum"] = updated_sum.tolist()
    person_entry["_total_weight"] = updated_weight
    person_entry["centroid"] = updated_centroid.tolist()
    person_entry.setdefault("image_paths", []).extend(sample["image_path"] for sample in cluster["samples"])
    person_entry.setdefault("image_created_ats", []).extend(sample["created_at"] for sample in cluster["samples"])
    person_entry.setdefault("face_boxes", []).extend(sample["face_box"] for sample in cluster["samples"])
    person_entry.setdefault("quality_scores", []).extend(float(sample["quality_score"]) for sample in cluster["samples"])
    person_entry["_top_faces"] = _trim_top_faces(person_entry.get("_top_faces", []) + _top_face_entries_from_samples(cluster["samples"]))
    person_entry["count"] = len(person_entry["image_paths"])

    person_vs.remove_ids(np.array([person_id], dtype=np.int64))
    person_vs.add_with_ids(embedding_row(updated_centroid), np.array([person_id], dtype=np.int64))


def _blank_candidate(person_id: int) -> dict[str, Any]:
    return {
        "person_id": person_id,
        "person_hits": 0,
        "face_hits": 0,
        "person_score_sum": 0.0,
        "face_score_sum": 0.0,
        "best_person_score": float("-inf"),
        "best_face_score": float("-inf"),
        "avg_person_score": float("-inf"),
        "avg_face_score": float("-inf"),
        "best_score": float("-inf"),
    }


def _rank_person_candidates(
    query_embedding: torch.Tensor,
    *,
    exclude_person_ids: set[int] | None = None,
    min_score: float = FACE_MERGE_THRESHOLD,
) -> list[dict[str, Any]]:
    excluded = exclude_person_ids or set()
    query_row = embedding_row(_normalize_embedding(query_embedding))
    candidates: dict[int, dict[str, Any]] = {}

    person_vector_store, _ = load_person_vector_store()
    if person_vector_store.ntotal > 0:
        person_k = min(max(FACE_ASSIGNMENT_TOP_K + len(excluded), FACE_ASSIGNMENT_TOP_K), int(person_vector_store.ntotal))
        person_scores, person_ids = person_vector_store.search(query_row, k=person_k)
        for score, person_id in zip(person_scores[0], person_ids[0]):
            resolved_person_id = int(person_id)
            resolved_score = float(score)
            if resolved_person_id < 0 or resolved_person_id in excluded or resolved_score < min_score:
                continue

            candidate = candidates.setdefault(resolved_person_id, _blank_candidate(resolved_person_id))
            candidate["person_hits"] += 1
            candidate["person_score_sum"] += resolved_score
            candidate["best_person_score"] = max(candidate["best_person_score"], resolved_score)

    face_vector_store, face_store_meta_data = load_face_vector_store()
    if face_vector_store.ntotal > 0:
        face_k = min(max(FACE_ASSIGNMENT_TOP_K * 4, FACE_ASSIGNMENT_TOP_K), int(face_vector_store.ntotal))
        face_scores, face_ids = face_vector_store.search(query_row, k=face_k)
        for score, face_id in zip(face_scores[0], face_ids[0]):
            resolved_face_id = int(face_id)
            resolved_score = float(score)
            if resolved_face_id < 0 or resolved_score < min_score:
                continue

            face_entry = face_store_meta_data.get(str(resolved_face_id))
            if not isinstance(face_entry, dict):
                continue

            resolved_person_id = int(face_entry.get("person_id", -1))
            if resolved_person_id < 0 or resolved_person_id in excluded:
                continue

            candidate = candidates.setdefault(resolved_person_id, _blank_candidate(resolved_person_id))
            candidate["face_hits"] += 1
            candidate["face_score_sum"] += resolved_score
            candidate["best_face_score"] = max(candidate["best_face_score"], resolved_score)

    ranked_candidates = []
    for candidate in candidates.values():
        if candidate["person_hits"] > 0:
            candidate["avg_person_score"] = candidate["person_score_sum"] / candidate["person_hits"]
        if candidate["face_hits"] > 0:
            candidate["avg_face_score"] = candidate["face_score_sum"] / candidate["face_hits"]
        candidate["best_score"] = max(candidate["best_person_score"], candidate["best_face_score"])
        ranked_candidates.append(candidate)

    ranked_candidates.sort(
        key=lambda candidate: (
            candidate["face_hits"],
            candidate["best_score"],
            candidate["avg_face_score"],
            candidate["avg_person_score"],
            candidate["person_hits"],
        ),
        reverse=True,
    )
    return ranked_candidates


def _should_assign_candidate(candidate: dict[str, Any] | None) -> bool:
    if candidate is None:
        return False
    if candidate["face_hits"] >= 2 and candidate["avg_face_score"] >= FACE_MERGE_THRESHOLD:
        return True
    if candidate["best_person_score"] >= FACE_STRONG_MATCH_THRESHOLD:
        return True
    return (
        candidate["face_hits"] >= 1
        and candidate["best_face_score"] >= FACE_STRONG_MATCH_THRESHOLD
        and candidate["best_person_score"] >= FACE_MERGE_THRESHOLD
    )


def _should_merge_candidate(candidate: dict[str, Any] | None) -> bool:
    if candidate is None:
        return False
    if candidate["face_hits"] >= 2 and max(candidate["avg_face_score"], candidate["best_person_score"]) >= FACE_POST_MERGE_THRESHOLD:
        return True
    return candidate["best_person_score"] >= FACE_POST_MERGE_THRESHOLD and candidate["best_face_score"] >= FACE_MERGE_THRESHOLD


def _preferred_merge_pair(person_a: int, person_b: int, person_meta_data: dict[str, Any]) -> tuple[int, int]:
    entry_a = _ensure_person_state(person_meta_data[str(person_a)])
    entry_b = _ensure_person_state(person_meta_data[str(person_b)])

    if entry_a.get("name") and not entry_b.get("name"):
        return person_a, person_b
    if entry_b.get("name") and not entry_a.get("name"):
        return person_b, person_a

    weight_a = float(entry_a.get("_total_weight", entry_a.get("count", 1)))
    weight_b = float(entry_b.get("_total_weight", entry_b.get("count", 1)))
    if weight_a > weight_b:
        return person_a, person_b
    if weight_b > weight_a:
        return person_b, person_a

    return (person_a, person_b) if person_a <= person_b else (person_b, person_a)


def _merge_person_entries(target_id: int, source_id: int, person_meta_data: dict[str, Any], face_meta_data: dict[str, Any]) -> None:
    if target_id == source_id:
        return

    target_entry = _ensure_person_state(person_meta_data[str(target_id)])
    source_entry = _ensure_person_state(person_meta_data[str(source_id)])

    merged_sum = torch.tensor(target_entry["_embedding_sum"], dtype=torch.float32) + torch.tensor(source_entry["_embedding_sum"], dtype=torch.float32)
    merged_weight = float(target_entry["_total_weight"]) + float(source_entry["_total_weight"])
    merged_centroid = _normalize_embedding(merged_sum)

    target_entry["_embedding_sum"] = merged_sum.tolist()
    target_entry["_total_weight"] = merged_weight
    target_entry["centroid"] = merged_centroid.tolist()
    target_entry.setdefault("image_paths", []).extend(source_entry.get("image_paths", []))
    target_entry.setdefault("image_created_ats", []).extend(source_entry.get("image_created_ats", []))
    target_entry.setdefault("face_boxes", []).extend(source_entry.get("face_boxes", []))
    target_entry.setdefault("quality_scores", []).extend(source_entry.get("quality_scores", []))
    target_entry["_top_faces"] = _trim_top_faces(target_entry.get("_top_faces", []) + source_entry.get("_top_faces", []))
    if not target_entry.get("name") and source_entry.get("name"):
        target_entry["name"] = source_entry["name"]
    target_entry["count"] = len(target_entry["image_paths"])

    for key, face_entry in face_meta_data.items():
        if str(key).startswith("_") or not isinstance(face_entry, dict):
            continue
        if int(face_entry.get("person_id", -1)) == source_id:
            face_entry["person_id"] = target_id

    del person_meta_data[str(source_id)]


def _merge_duplicate_people(face_meta_data: dict[str, Any], person_meta_data: dict[str, Any]) -> dict[str, Any]:
    merged_pairs: list[tuple[int, int]] = []
    _rebuild_person_index(person_meta_data)

    while True:
        person_ids = sorted(int(key) for key in person_meta_data.keys() if not str(key).startswith("_"))
        did_merge = False

        for person_id in person_ids:
            person_entry = person_meta_data.get(str(person_id))
            if not isinstance(person_entry, dict):
                continue

            candidate_list = _rank_person_candidates(
                torch.tensor(person_entry["centroid"], dtype=torch.float32),
                exclude_person_ids={person_id},
                min_score=FACE_MERGE_THRESHOLD,
            )
            best_candidate = candidate_list[0] if candidate_list else None
            if not _should_merge_candidate(best_candidate):
                continue

            winner_id, loser_id = _preferred_merge_pair(person_id, int(best_candidate["person_id"]), person_meta_data)
            if str(loser_id) not in person_meta_data:
                continue

            _merge_person_entries(winner_id, loser_id, person_meta_data, face_meta_data)
            _rebuild_person_index(person_meta_data)
            merged_pairs.append((winner_id, loser_id))
            did_merge = True
            break

        if not did_merge:
            break

    merged_person_ids = sorted({winner_id for winner_id, _ in merged_pairs})
    return {
        "merged_person_count": len(merged_pairs),
        "merged_person_ids": merged_person_ids,
    }


def _collect_final_merge_candidate_ids(person_id: int, person_meta_data: dict[str, Any]) -> list[int]:
    person_entry = _ensure_person_state(person_meta_data[str(person_id)])
    query_embeddings = [torch.tensor(person_entry["centroid"], dtype=torch.float32), *_top_face_embeddings(person_entry)]
    candidate_ids: set[int] = set()

    person_vector_store, _ = load_person_vector_store()
    if person_vector_store.ntotal == 0:
        return []

    search_k = min(max(FACE_ASSIGNMENT_TOP_K * 2, 8), int(person_vector_store.ntotal))
    for query_embedding in query_embeddings:
        scores, ids = person_vector_store.search(embedding_row(_normalize_embedding(query_embedding)), k=search_k)
        for score, candidate_id in zip(scores[0], ids[0]):
            resolved_candidate_id = int(candidate_id)
            if resolved_candidate_id < 0 or resolved_candidate_id == person_id:
                continue
            if float(score) < FACE_MERGE_THRESHOLD:
                continue
            candidate_ids.add(resolved_candidate_id)

    return sorted(candidate_ids)


def _best_match_average(source_embeddings: list[torch.Tensor], target_embeddings: list[torch.Tensor]) -> float:
    if not source_embeddings or not target_embeddings:
        return float("-inf")

    best_scores = []
    for source_embedding in source_embeddings:
        best_scores.append(max(float(torch.dot(source_embedding, target_embedding)) for target_embedding in target_embeddings))
    return sum(best_scores) / len(best_scores)


def _compare_person_entries(person_a: int, person_b: int, person_meta_data: dict[str, Any]) -> dict[str, Any]:
    entry_a = _ensure_person_state(person_meta_data[str(person_a)])
    entry_b = _ensure_person_state(person_meta_data[str(person_b)])

    centroid_a = torch.tensor(entry_a["centroid"], dtype=torch.float32)
    centroid_b = torch.tensor(entry_b["centroid"], dtype=torch.float32)
    top_faces_a = _top_face_embeddings(entry_a)
    top_faces_b = _top_face_embeddings(entry_b)

    pair_scores = [
        float(torch.dot(face_a, face_b))
        for face_a in top_faces_a
        for face_b in top_faces_b
    ]
    best_exemplar_score = max(pair_scores) if pair_scores else float("-inf")
    avg_exemplar_score = (
        _best_match_average(top_faces_a, top_faces_b) + _best_match_average(top_faces_b, top_faces_a)
    ) / 2.0
    centroid_score = float(torch.dot(centroid_a, centroid_b))
    combined_score = (centroid_score + best_exemplar_score + avg_exemplar_score) / 3.0

    return {
        "person_id": person_b,
        "centroid_score": centroid_score,
        "best_exemplar_score": best_exemplar_score,
        "avg_exemplar_score": avg_exemplar_score,
        "combined_score": combined_score,
    }


def _should_merge_people_final(candidate: dict[str, Any] | None) -> bool:
    if candidate is None:
        return False
    if candidate["centroid_score"] < FACE_FINAL_MERGE_CENTROID_THRESHOLD:
        return False
    return (
        candidate["best_exemplar_score"] >= FACE_FINAL_MERGE_EXEMPLAR_THRESHOLD
        or candidate["avg_exemplar_score"] >= FACE_FINAL_MERGE_AVG_EXEMPLAR_THRESHOLD
    )


def finalize_face_clusters() -> dict[str, Any]:
    face_vector_store, face_store_meta_data = load_face_vector_store()
    person_vector_store, person_store_meta_data = load_person_vector_store()
    stats = {
        "merged_person_count": 0,
        "merged_person_ids": [],
        "person_store_total": int(person_vector_store.ntotal),
        "face_store_total": int(face_vector_store.ntotal),
    }

    if person_vector_store.ntotal <= 1:
        return stats

    _rebuild_person_index(person_store_meta_data)
    merged_pairs: list[tuple[int, int]] = []

    while True:
        person_ids = sorted(int(key) for key in person_store_meta_data.keys() if not str(key).startswith("_"))
        did_merge = False

        for person_id in person_ids:
            if str(person_id) not in person_store_meta_data:
                continue

            candidate_metrics = [
                _compare_person_entries(person_id, candidate_id, person_store_meta_data)
                for candidate_id in _collect_final_merge_candidate_ids(person_id, person_store_meta_data)
                if str(candidate_id) in person_store_meta_data
            ]
            candidate_metrics.sort(
                key=lambda candidate: (
                    candidate["combined_score"],
                    candidate["best_exemplar_score"],
                    candidate["avg_exemplar_score"],
                    candidate["centroid_score"],
                ),
                reverse=True,
            )

            best_candidate = candidate_metrics[0] if candidate_metrics else None
            if not _should_merge_people_final(best_candidate):
                continue

            winner_id, loser_id = _preferred_merge_pair(person_id, int(best_candidate["person_id"]), person_store_meta_data)
            if str(loser_id) not in person_store_meta_data:
                continue

            _merge_person_entries(winner_id, loser_id, person_store_meta_data, face_store_meta_data)
            _rebuild_person_index(person_store_meta_data)
            merged_pairs.append((winner_id, loser_id))
            did_merge = True
            break

        if not did_merge:
            break

    stats["merged_person_count"] = len(merged_pairs)
    stats["merged_person_ids"] = sorted({winner_id for winner_id, _ in merged_pairs})
    stats["person_store_total"] = int(load_person_vector_store()[0].ntotal)
    stats["face_store_total"] = int(load_face_vector_store()[0].ntotal)
    return stats


def add_faces_to_vector_store(
    path_2_embeddings: dict[Path, torch.Tensor],
    path_2_boxes: dict[Path, list],
    *,
    path_2_created_at: dict[Path, str | None] | None = None,
):
    face_vector_store, face_store_meta_data = load_face_vector_store()
    person_vector_store, person_store_meta_data = load_person_vector_store()
    stats = {
        "indexed_face_count": 0,
        "new_person_count": 0,
        "assigned_person_ids": [],
        "batch_cluster_count": 0,
        "merged_person_count": 0,
        "merged_person_ids": [],
    }

    face_samples = _flatten_face_samples(
        path_2_embeddings,
        path_2_boxes,
        path_2_created_at=path_2_created_at,
    )
    if not face_samples:
        stats["assigned_person_count"] = 0
        stats["person_store_total"] = int(person_vector_store.ntotal)
        stats["face_store_total"] = int(face_vector_store.ntotal)
        return stats

    face_clusters = _cluster_face_samples(face_samples)
    stats["batch_cluster_count"] = len(face_clusters)

    added_face_ids: list[int] = []
    for cluster in face_clusters:
        ranked_candidates = _rank_person_candidates(cluster["centroid"])
        best_candidate = ranked_candidates[0] if ranked_candidates else None

        if _should_assign_candidate(best_candidate):
            person_id = int(best_candidate["person_id"])
            _merge_cluster_into_person(person_id, cluster, person_store_meta_data, person_vector_store)
        else:
            person_id = consume_next_id(person_store_meta_data)
            person_store_meta_data[str(person_id)] = _person_entry_from_cluster(cluster)
            person_vector_store.add_with_ids(
                embedding_row(cluster["centroid"]),
                np.array([person_id], dtype=np.int64),
            )
            stats["new_person_count"] += 1

        for sample in cluster["samples"]:
            face_id = consume_next_id(face_store_meta_data)
            face_vector_store.add_with_ids(
                embedding_row(sample["embedding"]),
                np.array([face_id], dtype=np.int64),
            )
            face_store_meta_data[str(face_id)] = {
                "person_id": person_id,
                "image_path": sample["image_path"],
                "created_at": sample["created_at"],
                "face_box": sample["face_box"],
                "quality_score": float(sample["quality_score"]),
            }
            stats["indexed_face_count"] += 1
            added_face_ids.append(face_id)

    merge_stats = _merge_duplicate_people(face_store_meta_data, person_store_meta_data)
    stats.update(merge_stats)

    if added_face_ids:
        stats["assigned_person_ids"] = sorted(
            {
                int(face_store_meta_data[str(face_id)]["person_id"])
                for face_id in added_face_ids
                if str(face_id) in face_store_meta_data
            }
        )
    stats["assigned_person_count"] = len(stats["assigned_person_ids"])

    refreshed_person_store, _ = load_person_vector_store()
    refreshed_face_store, _ = load_face_vector_store()
    stats["person_store_total"] = int(refreshed_person_store.ntotal)
    stats["face_store_total"] = int(refreshed_face_store.ntotal)
    return stats

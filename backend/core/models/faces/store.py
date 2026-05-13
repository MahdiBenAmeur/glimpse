from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
import threading
from typing import Any, Callable

import faiss
import numpy as np
from PIL import Image
from sklearn.cluster import DBSCAN
import torch

from backend.config import (
    FACE_MAX_QUALITY_SCORE,
    FACE_PIPELINE_DBSCAN_EPS,
    FACE_PIPELINE_DBSCAN_MIN_SAMPLES,
    FACE_QUALITY_REFERENCE_PIXELS,
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


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Vector store lifecycle
# ---------------------------------------------------------------------------

def reset_face_vector_stores() -> None:
    """Clear cached face and person stores so subsequent calls reload from disk."""
    global face_vs, face_meta_data, person_vs, person_meta_data
    _log_face_store(
        "Resetting cached face stores",
        had_face_vs=face_vs is not None,
        had_face_meta_data=face_meta_data is not None,
        had_person_vs=person_vs is not None,
        had_person_meta_data=person_meta_data is not None,
    )
    face_vs = None
    face_meta_data = None
    person_vs = None
    person_meta_data = None


def load_face_vector_store():
    """Load or initialize the face-level vector store and metadata cache."""
    global face_vs, face_meta_data
    if face_vs is not None and face_meta_data is not None:
        return face_vs, face_meta_data
    _log_face_store("Loading face vector store from disk")
    face_vs, face_meta_data = load_or_init_vector_store(FACE_VS_PATH, emb_dim=face_emb_dim)
    _log_face_store(
        "Loaded face vector store from disk",
        ntotal=int(face_vs.ntotal),
        metadata_entry_count=len(face_meta_data),
    )
    return face_vs, face_meta_data


def load_person_vector_store():
    """Load or initialize the person-level vector store and metadata cache."""
    global person_vs, person_meta_data
    if person_vs is not None and person_meta_data is not None:
        return person_vs, person_meta_data
    _log_face_store("Loading person vector store from disk")
    person_vs, person_meta_data = load_or_init_vector_store(PERSON_VS_PATH, emb_dim=face_emb_dim)
    _log_face_store(
        "Loaded person vector store from disk",
        ntotal=int(person_vs.ntotal),
        metadata_entry_count=len(person_meta_data),
    )
    return person_vs, person_meta_data


def save_face_vector_stores() -> None:
    """Persist both face-level and person-level vector stores to disk."""
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


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

def _normalize_embedding(embedding: torch.Tensor) -> torch.Tensor:
    """Convert an embedding to a 1D normalized float32 CPU tensor."""
    vector = embedding.detach().cpu().to(torch.float32).reshape(-1)
    norm = vector.norm().clamp_min(1e-12)
    return vector / norm


def _empty_index() -> faiss.IndexIDMap2:
    """Create an empty inner-product FAISS index with explicit ids."""
    return faiss.IndexIDMap2(faiss.IndexFlatIP(face_emb_dim))


# ---------------------------------------------------------------------------
# Face quality scoring
# ---------------------------------------------------------------------------

def _face_box_area(face_box: list[float]) -> float:
    left, top, right, bottom = [float(v) for v in face_box]
    return max(right - left, 1.0) * max(bottom - top, 1.0)


def _face_quality_weight(face_box: list[float]) -> float:
    """Score a face by box size, capped to avoid oversized faces dominating."""
    area = _face_box_area(face_box)
    return min(FACE_MAX_QUALITY_SCORE, max(1.0, math.sqrt(area / FACE_QUALITY_REFERENCE_PIXELS)))


def _face_sharpness_weight(image_path: Path, face_box: list[float]) -> float:
    """Estimate crop sharpness from local pixel variation for exemplar ranking."""
    try:
        with Image.open(image_path) as image:
            left, top, right, bottom = [float(v) for v in face_box]
            crop_box = (
                max(0, int(math.floor(left))),
                max(0, int(math.floor(top))),
                min(image.width, int(math.ceil(right))),
                min(image.height, int(math.ceil(bottom))),
            )
            if crop_box[2] - crop_box[0] < 2 or crop_box[3] - crop_box[1] < 2:
                return 1.0
            crop = image.convert("L").crop(crop_box)
            pixels = np.asarray(crop, dtype=np.float32)
            if pixels.size == 0:
                return 1.0
            sharpness = float(np.diff(pixels, axis=1).var() + np.diff(pixels, axis=0).var())
    except Exception:
        return 1.0
    return 1.0 + min(1.0, math.log1p(max(sharpness, 0.0)) / 8.0)


def _face_quality_score(image_path: Path, face_box: list[float], detection_confidence: float = 1.0) -> float:
    """Combine size, sharpness, and detector confidence into one face quality score."""
    confidence = min(1.0, max(0.0, float(detection_confidence)))
    confidence_weight = 0.75 + (confidence * 0.5)
    quality = _face_quality_weight(face_box) * _face_sharpness_weight(image_path, face_box) * confidence_weight
    return min(FACE_MAX_QUALITY_SCORE, max(1.0, quality))


# ---------------------------------------------------------------------------
# Face sample construction
# ---------------------------------------------------------------------------

def _make_face_sample(
    *,
    image_path: Path,
    embedding: torch.Tensor,
    face_box: list[float],
    created_at: str | None,
    detection_confidence: float = 1.0,
    face_id: int | None = None,
) -> dict[str, Any]:
    """Create the canonical in-memory representation of one detected face."""
    return {
        "face_id": face_id,
        "image_path": str(image_path),
        "embedding": _normalize_embedding(embedding),
        "face_box": [float(v) for v in face_box],
        "created_at": created_at,
        "detection_confidence": float(detection_confidence),
        "quality_score": _face_quality_score(image_path, face_box, detection_confidence),
    }


def _flatten_face_samples(
    path_2_embeddings: dict[Path, torch.Tensor],
    path_2_boxes: dict[Path, list],
    *,
    path_2_created_at: dict[Path, str | None] | None,
) -> list[dict[str, Any]]:
    """Pair detected boxes with embeddings and flatten them into face samples.

    The detector and embedder both keep image-path groupings, so this method
    joins boxes and embeddings by path and position. Any embedding without a
    matching box is ignored to avoid writing incomplete face metadata.
    """
    samples: list[dict[str, Any]] = []
    for image_path, embeddings in path_2_embeddings.items():
        boxes = path_2_boxes.get(image_path, [])
        created_at = path_2_created_at.get(image_path) if path_2_created_at is not None else None
        for index, embedding in enumerate(embeddings):
            if index >= len(boxes):
                continue
            box = boxes[index]
            detection_confidence = float(box.conf[0]) if getattr(box, "conf", None) is not None else 1.0
            samples.append(
                _make_face_sample(
                    image_path=image_path,
                    embedding=embedding,
                    face_box=box.xyxy[0].tolist(),
                    created_at=created_at,
                    detection_confidence=detection_confidence,
                )
            )
    return samples


# ---------------------------------------------------------------------------
# Top-face exemplar management
# ---------------------------------------------------------------------------

def _make_top_face_entry(sample: dict[str, Any]) -> dict[str, Any]:
    """Convert a face sample into a serializable exemplar entry."""
    return {
        "face_id": sample.get("face_id"),
        "embedding": _normalize_embedding(sample["embedding"]).tolist(),
        "quality_score": float(sample.get("quality_score", 1.0)),
        "image_path": sample["image_path"],
        "face_box": list(sample.get("face_box", [])),
        "created_at": sample.get("created_at"),
        "detection_confidence": float(sample.get("detection_confidence", 1.0)),
    }


def _normalize_top_face_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Validate and normalize a stored exemplar entry, dropping invalid ones."""
    if not isinstance(entry, dict):
        return None
    embedding = entry.get("embedding")
    if not isinstance(embedding, list) or len(embedding) != face_emb_dim:
        return None
    return {
        "face_id": entry.get("face_id"),
        "embedding": _normalize_embedding(torch.tensor(embedding, dtype=torch.float32)).tolist(),
        "quality_score": float(entry.get("quality_score", 1.0)),
        "image_path": str(entry.get("image_path", "")),
        "face_box": [float(v) for v in entry.get("face_box", [])],
        "created_at": entry.get("created_at"),
        "detection_confidence": float(entry.get("detection_confidence", 1.0)),
    }


def _trim_top_faces(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate exemplar faces and keep the highest-quality entries."""
    normalized_entries = []
    seen: set[tuple[str, tuple[float, ...]]] = set()
    for entry in entries:
        normalized_entry = _normalize_top_face_entry(entry)
        if normalized_entry is None:
            continue
        dedupe_key = (
            normalized_entry.get("image_path", ""),
            tuple(round(float(v), 4) for v in normalized_entry.get("face_box", [])),
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized_entries.append(normalized_entry)
    normalized_entries.sort(key=lambda e: float(e["quality_score"]), reverse=True)
    return normalized_entries[:FACE_TOP_EXEMPLAR_COUNT]


# ---------------------------------------------------------------------------
# Person store helpers
# ---------------------------------------------------------------------------

def _iter_data_entries(meta_data: dict[str, Any]):
    """Yield numeric metadata entries while skipping reserved underscore keys."""
    for key, entry in meta_data.items():
        if str(key).startswith("_") or not isinstance(entry, dict):
            continue
        yield int(key), entry


def _empty_person_metadata() -> dict[str, Any]:
    return {"_next_id": 0}


def _reset_person_store_in_memory() -> tuple[faiss.IndexIDMap2, dict[str, Any]]:
    """Replace the cached person store with a fresh empty in-memory store."""
    global person_vs, person_meta_data
    person_vs = _empty_index()
    person_meta_data = _empty_person_metadata()
    return person_vs, person_meta_data


def _ensure_person_state(entry: dict[str, Any]) -> dict[str, Any]:
    """Backfill and normalize person metadata fields expected by current code.

    Older or partial person records may be missing weighted sums, face ids, or
    exemplar data. This function reconstructs safe defaults, normalizes the
    centroid, preserves stored lists, and leaves the entry ready for indexing or
    mutation by merge/add operations.
    """
    image_paths = list(entry.get("image_paths", []))
    face_boxes = list(entry.get("face_boxes", []))
    image_created_ats = list(entry.get("image_created_ats", []))
    quality_scores = [float(v) for v in entry.get("quality_scores", [])]
    face_ids = []
    for raw_face_id in entry.get("_face_ids", []):
        try:
            face_ids.append(int(raw_face_id))
        except (TypeError, ValueError):
            continue
    count = max(int(entry.get("count", 0)), len(image_paths), len(face_boxes), len(face_ids), 1)

    centroid_raw = entry.get("centroid")
    if isinstance(centroid_raw, list) and len(centroid_raw) == face_emb_dim:
        centroid = _normalize_embedding(torch.tensor(centroid_raw, dtype=torch.float32))
    else:
        centroid = torch.zeros(face_emb_dim, dtype=torch.float32)
        centroid[0] = 1.0

    embedding_sum_raw = entry.get("_embedding_sum")
    if isinstance(embedding_sum_raw, list) and len(embedding_sum_raw) == face_emb_dim:
        embedding_sum = torch.tensor(embedding_sum_raw, dtype=torch.float32)
    else:
        embedding_sum = centroid * max(float(entry.get("_total_weight", count)), 1.0)

    total_weight = max(float(entry.get("_total_weight", count)), 1.0)
    entry["count"] = count
    entry["centroid"] = _normalize_embedding(embedding_sum).tolist()
    entry["_embedding_sum"] = embedding_sum.tolist()
    entry["_total_weight"] = total_weight
    entry["image_paths"] = image_paths
    entry["image_created_ats"] = image_created_ats
    entry["face_boxes"] = face_boxes
    entry["quality_scores"] = quality_scores
    entry["_face_ids"] = face_ids
    entry["_top_faces"] = _trim_top_faces(entry.get("_top_faces", []))
    return entry


def _new_person_entry(sample: dict[str, Any]) -> dict[str, Any]:
    """Create a person metadata entry seeded from the first face sample."""
    weight = float(sample.get("quality_score", 1.0))
    embedding_sum = _normalize_embedding(sample["embedding"]) * weight
    face_id = sample.get("face_id")
    return {
        "count": 1,
        "centroid": _normalize_embedding(embedding_sum).tolist(),
        "image_paths": [sample["image_path"]],
        "image_created_ats": [sample.get("created_at")],
        "face_boxes": [sample.get("face_box", [])],
        "quality_scores": [weight],
        "_embedding_sum": embedding_sum.tolist(),
        "_total_weight": weight,
        "_face_ids": [int(face_id)] if face_id is not None else [],
        "_top_faces": _trim_top_faces([_make_top_face_entry(sample)]),
    }


def _add_sample_to_person_entry(entry: dict[str, Any], sample: dict[str, Any]) -> None:
    """Update a person centroid and metadata with another face sample."""
    person_entry = _ensure_person_state(entry)
    weight = float(sample.get("quality_score", 1.0))
    embedding_sum = (
        torch.tensor(person_entry["_embedding_sum"], dtype=torch.float32)
        + (_normalize_embedding(sample["embedding"]) * weight)
    )
    total_weight = float(person_entry["_total_weight"]) + weight
    person_entry["_embedding_sum"] = embedding_sum.tolist()
    person_entry["_total_weight"] = total_weight
    person_entry["centroid"] = _normalize_embedding(embedding_sum).tolist()
    person_entry.setdefault("image_paths", []).append(sample["image_path"])
    person_entry.setdefault("image_created_ats", []).append(sample.get("created_at"))
    person_entry.setdefault("face_boxes", []).append(sample.get("face_box", []))
    person_entry.setdefault("quality_scores", []).append(weight)
    if sample.get("face_id") is not None:
        person_entry.setdefault("_face_ids", []).append(int(sample["face_id"]))
    person_entry["_top_faces"] = _trim_top_faces(
        person_entry.get("_top_faces", []) + [_make_top_face_entry(sample)]
    )
    person_entry["count"] = len(person_entry["image_paths"])


def _rebuild_person_index(person_store_meta_data: dict[str, Any]):
    """Recreate the person FAISS index from centroid metadata."""
    global person_vs
    rebuilt_index = _empty_index()
    for key in sorted(
        (item for item in person_store_meta_data.keys() if not str(item).startswith("_")), key=int
    ):
        entry = person_store_meta_data.get(str(key))
        if not isinstance(entry, dict):
            continue
        person_entry = _ensure_person_state(entry)
        rebuilt_index.add_with_ids(
            embedding_row(torch.tensor(person_entry["centroid"], dtype=torch.float32)),
            np.array([int(key)], dtype=np.int64),
        )
    person_vs = rebuilt_index
    return rebuilt_index


def _all_face_samples(face_vector_store, face_store_meta_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Reconstruct all indexed face vectors into sample dictionaries."""
    samples = []
    for face_id, face_entry in _iter_data_entries(face_store_meta_data):
        try:
            raw = face_vector_store.reconstruct(int(face_id))
            embedding = _normalize_embedding(torch.tensor(raw, dtype=torch.float32))
        except Exception:
            continue
        face_box = [float(v) for v in face_entry.get("face_box", [])]
        samples.append({
            "face_id": face_id,
            "image_path": str(face_entry.get("image_path", "")),
            "embedding": embedding,
            "face_box": face_box,
            "created_at": face_entry.get("created_at"),
            "detection_confidence": float(face_entry.get("detection_confidence", 1.0)),
            "quality_score": float(face_entry.get("quality_score", _face_quality_weight(face_box) if face_box else 1.0)),
        })
    return samples


# ---------------------------------------------------------------------------
# Named-person preservation across re-clusters
# ---------------------------------------------------------------------------

def _collect_named_people(person_store_meta_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Capture named people before reclustering so names can be restored."""
    named_people = []
    for person_id, entry in _iter_data_entries(person_store_meta_data):
        name = entry.get("name")
        if not name:
            continue
        named_people.append({
            "person_id": person_id,
            "name": name,
            "image_paths": set(str(p) for p in entry.get("image_paths", []) if p),
        })
    return named_people


def _restore_named_people(named_people: list[dict[str, Any]], person_store_meta_data: dict[str, Any]) -> None:
    """Reapply saved names to the new clusters with the most image overlap."""
    used_person_ids: set[int] = set()
    for named_person in named_people:
        best_person_id = None
        best_overlap = 0
        named_paths = named_person["image_paths"]
        if not named_paths:
            continue
        for person_id, entry in _iter_data_entries(person_store_meta_data):
            if person_id in used_person_ids or entry.get("name"):
                continue
            overlap = len(named_paths.intersection(str(p) for p in entry.get("image_paths", []) if p))
            if overlap > best_overlap:
                best_overlap = overlap
                best_person_id = person_id
        if best_person_id is not None and best_overlap > 0:
            person_store_meta_data[str(best_person_id)]["name"] = named_person["name"]
            used_person_ids.add(best_person_id)


def _assign_faces_to_people(face_store_meta_data: dict[str, Any], person_store_meta_data: dict[str, Any]) -> None:
    """Synchronize each face metadata entry with its current person assignment."""
    for _, face_entry in _iter_data_entries(face_store_meta_data):
        face_entry["person_id"] = None
    for person_id, entry in _iter_data_entries(person_store_meta_data):
        for raw_face_id in entry.get("_face_ids", []):
            try:
                face_id = int(raw_face_id)
            except (TypeError, ValueError):
                continue
            face_entry = face_store_meta_data.get(str(face_id))
            if isinstance(face_entry, dict):
                face_entry["person_id"] = person_id


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def _merge_person_entries(
    target_id: int,
    source_id: int,
    person_store_meta_data: dict[str, Any],
    face_store_meta_data: dict[str, Any] | None = None,
) -> None:
    """Merge source person metadata into target and update face assignments.

    Centroids are merged through their stored weighted embedding sums rather
    than by averaging already-normalized centroids. Metadata lists and exemplar
    faces are concatenated, the best name is preserved, and any face metadata
    pointing at the source id is retargeted before the source entry is removed.
    """
    if target_id == source_id:
        return
    target_entry = _ensure_person_state(person_store_meta_data[str(target_id)])
    source_entry = _ensure_person_state(person_store_meta_data[str(source_id)])

    merged_sum = (
        torch.tensor(target_entry["_embedding_sum"], dtype=torch.float32)
        + torch.tensor(source_entry["_embedding_sum"], dtype=torch.float32)
    )
    merged_weight = float(target_entry["_total_weight"]) + float(source_entry["_total_weight"])
    target_entry["_embedding_sum"] = merged_sum.tolist()
    target_entry["_total_weight"] = merged_weight
    target_entry["centroid"] = _normalize_embedding(merged_sum).tolist()
    target_entry.setdefault("image_paths", []).extend(source_entry.get("image_paths", []))
    target_entry.setdefault("image_created_ats", []).extend(source_entry.get("image_created_ats", []))
    target_entry.setdefault("face_boxes", []).extend(source_entry.get("face_boxes", []))
    target_entry.setdefault("quality_scores", []).extend(source_entry.get("quality_scores", []))
    target_entry.setdefault("_face_ids", []).extend(source_entry.get("_face_ids", []))
    target_entry["_top_faces"] = _trim_top_faces(
        target_entry.get("_top_faces", []) + source_entry.get("_top_faces", [])
    )
    if not target_entry.get("name") and source_entry.get("name"):
        target_entry["name"] = source_entry["name"]
    target_entry["count"] = len(target_entry["image_paths"])

    if face_store_meta_data is not None:
        source_face_ids = {int(fid) for fid in source_entry.get("_face_ids", [])}
        if source_face_ids:
            for fid in source_face_ids:
                face_entry = face_store_meta_data.get(str(fid))
                if isinstance(face_entry, dict):
                    face_entry["person_id"] = target_id
        else:
            for _, face_entry in _iter_data_entries(face_store_meta_data):
                if face_entry.get("person_id") is not None and int(face_entry["person_id"]) == source_id:
                    face_entry["person_id"] = target_id

    del person_store_meta_data[str(source_id)]


# ---------------------------------------------------------------------------
# DBSCAN clustering pipeline
# ---------------------------------------------------------------------------

def _cluster_face_samples_dbscan(
    samples: list[dict[str, Any]],
    face_store_meta_data: dict[str, Any],
    *,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Cluster face samples into people using DBSCAN on cosine distance.

    Embeddings are normalized and stacked into a matrix, then DBSCAN groups
    nearby faces without requiring a known person count. Labelled clusters
    become person entries, noise points (label == -1) stay unassigned, and face
    metadata is updated with the new person id for each assigned sample.
    """
    stats = {
        "processed_face_count": len(samples),
        "assigned_face_count": 0,
        "unknown_face_count": 0,
        "new_person_count": 0,
    }
    person_store_meta_data = _empty_person_metadata()

    for _, face_entry in _iter_data_entries(face_store_meta_data):
        face_entry["person_id"] = None

    if not samples:
        return person_store_meta_data, stats

    # Stack normalised embeddings into an (N, D) float32 matrix.
    matrix = np.stack(
        [_normalize_embedding(s["embedding"]).numpy() for s in samples],
        axis=0,
    ).astype(np.float32)

    if cancel_check is not None and cancel_check():
        return person_store_meta_data, {**stats, "cancelled": True}

    clustering = DBSCAN(
        eps=float(FACE_PIPELINE_DBSCAN_EPS),
        min_samples=int(FACE_PIPELINE_DBSCAN_MIN_SAMPLES),
        metric="cosine",
        n_jobs=-1,
    )
    labels: np.ndarray = clustering.fit_predict(matrix)

    if cancel_check is not None and cancel_check():
        return person_store_meta_data, {**stats, "cancelled": True}

    # Group sample indices by cluster label.
    clusters: dict[int, list[int]] = {}
    for idx, label in enumerate(labels):
        clusters.setdefault(int(label), []).append(idx)

    # Build person entries for every real cluster (label != -1).
    for label, indices in clusters.items():
        if label == -1:
            stats["unknown_face_count"] += len(indices)
            continue

        person_id = consume_next_id(person_store_meta_data)
        for idx in indices:
            sample = samples[idx]
            person_key = str(person_id)
            if person_key not in person_store_meta_data:
                person_store_meta_data[person_key] = _new_person_entry(sample)
            else:
                _add_sample_to_person_entry(person_store_meta_data[person_key], sample)

            face_id = sample.get("face_id")
            if face_id is not None:
                face_entry = face_store_meta_data.get(str(int(face_id)))
                if isinstance(face_entry, dict):
                    face_entry["person_id"] = person_id

            stats["assigned_face_count"] += 1

        stats["new_person_count"] += 1

    return person_store_meta_data, stats


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def merge_people(target_id: int, source_id: int) -> dict[str, Any]:
    """Merge two existing person clusters and persist the updated stores."""
    if target_id == source_id:
        raise ValueError("Cannot merge a person into itself")

    _, face_store_meta_data = load_face_vector_store()
    _, person_store_meta_data = load_person_vector_store()
    if not isinstance(person_store_meta_data.get(str(target_id)), dict):
        raise KeyError("Target person not found")
    if not isinstance(person_store_meta_data.get(str(source_id)), dict):
        raise KeyError("Source person not found")

    _merge_person_entries(target_id, source_id, person_store_meta_data, face_store_meta_data)
    _rebuild_person_index(person_store_meta_data)
    save_face_vector_stores()

    merged_entry = _ensure_person_state(person_store_meta_data[str(target_id)])
    return {
        "targetPersonId": target_id,
        "sourcePersonId": source_id,
        "imageCount": int(merged_entry.get("count", 0)),
        "name": merged_entry.get("name"),
    }


def finalize_face_clusters(cancel_check: Callable[[], bool] | None = None) -> dict[str, Any]:
    """Recluster all indexed faces into people and rebuild the person store.

    This is the consolidation pass after faces have been appended. It
    reconstructs every face vector, reclusters the full set, restores existing
    person names by image overlap, writes person ids back onto face metadata,
    and rebuilds the person-level FAISS index from the new centroids.
    """
    global person_meta_data

    face_vector_store, face_store_meta_data = load_face_vector_store()
    _, previous_person_meta_data = load_person_vector_store()
    named_people = _collect_named_people(previous_person_meta_data)

    stats = {
        "processed_face_count": 0,
        "assigned_face_count": 0,
        "unknown_face_count": 0,
        "new_person_count": 0,
        "merged_person_count": 0,
        "merged_person_ids": [],
        "person_store_total": 0,
        "face_store_total": int(face_vector_store.ntotal),
    }

    face_samples = _all_face_samples(face_vector_store, face_store_meta_data)
    clustered_person_meta_data, pipeline_stats = _cluster_face_samples_dbscan(
        face_samples,
        face_store_meta_data,
        cancel_check=cancel_check,
    )
    stats.update(pipeline_stats)
    if pipeline_stats.get("cancelled"):
        stats["cancelled"] = True
        return stats

    _restore_named_people(named_people, clustered_person_meta_data)
    _assign_faces_to_people(face_store_meta_data, clustered_person_meta_data)
    person_meta_data = clustered_person_meta_data
    rebuilt_person_store = _rebuild_person_index(clustered_person_meta_data)
    stats["merged_person_ids"] = sorted(
        person_id
        for person_id, entry in _iter_data_entries(clustered_person_meta_data)
        if int(entry.get("count", 0)) > 1
    )
    stats["person_store_total"] = int(rebuilt_person_store.ntotal)
    stats["face_store_total"] = int(face_vector_store.ntotal)
    return stats


def add_faces_to_vector_store(
    path_2_embeddings: dict[Path, torch.Tensor],
    path_2_boxes: dict[Path, list],
    *,
    path_2_created_at: dict[Path, str | None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
):
    """Append newly embedded faces to the face vector store and metadata.

    This function only writes face-level vectors and metadata. It intentionally
    leaves person assignment as None because clustering is done later by
    finalize_face_clusters, which considers the complete face store instead of
    making local decisions from a single batch.
    """
    face_vector_store, face_store_meta_data = load_face_vector_store()
    person_vector_store, _ = load_person_vector_store()
    stats = {
        "indexed_face_count": 0,
        "new_person_count": 0,
        "assigned_person_count": 0,
        "assigned_person_ids": [],
        "merged_person_count": 0,
        "merged_person_ids": [],
        "person_store_total": int(person_vector_store.ntotal),
        "face_store_total": int(face_vector_store.ntotal),
    }

    face_samples = _flatten_face_samples(
        path_2_embeddings,
        path_2_boxes,
        path_2_created_at=path_2_created_at,
    )
    if not face_samples:
        return stats

    for sample in face_samples:
        if cancel_check is not None and cancel_check():
            stats["cancelled"] = True
            break

        face_id = consume_next_id(face_store_meta_data)
        face_vector_store.add_with_ids(
            embedding_row(sample["embedding"]),
            np.array([face_id], dtype=np.int64),
        )
        face_store_meta_data[str(face_id)] = {
            "person_id": None,
            "image_path": sample["image_path"],
            "created_at": sample["created_at"],
            "face_box": sample["face_box"],
            "quality_score": float(sample["quality_score"]),
            "detection_confidence": float(sample.get("detection_confidence", 1.0)),
        }
        stats["indexed_face_count"] += 1

    stats["face_store_total"] = int(face_vector_store.ntotal)
    stats["person_store_total"] = int(person_vector_store.ntotal)
    return stats


def purge_face_entries(match_image_path: Callable[[str], bool]) -> dict[str, Any]:
    """Remove face vectors for matching image paths and rebuild person clusters.

    FAISS entries are rebuilt from the ids that remain, metadata is filtered in
    lockstep, and then people are reclustered from the surviving faces. If no
    faces remain, the person store is reset to an empty in-memory state.
    """
    global face_vs, face_meta_data

    if face_vs is None or face_meta_data is None:
        if not FACE_VS_PATH.exists():
            return {"removed_face_ids": [], "removed_face_count": 0, "remaining_face_count": 0, "remaining_person_count": 0}
        face_vs, face_meta_data = load_face_vector_store()

    load_person_vector_store()

    removed_face_ids: list[int] = []
    kept_face_ids: list[int] = []
    next_face_meta_data = {
        str(key): value
        for key, value in face_meta_data.items()
        if str(key).startswith("_")
    }

    for key, value in face_meta_data.items():
        if str(key).startswith("_") or not isinstance(value, dict):
            continue
        image_path = value.get("image_path")
        if image_path and match_image_path(str(image_path)):
            removed_face_ids.append(int(key))
            continue
        kept_face_ids.append(int(key))
        next_face_meta_data[str(key)] = value

    if not removed_face_ids:
        _, current_person_meta_data = load_person_vector_store()
        remaining_person_count = sum(1 for key in current_person_meta_data if not str(key).startswith("_"))
        return {
            "removed_face_ids": [],
            "removed_face_count": 0,
            "remaining_face_count": len(kept_face_ids),
            "remaining_person_count": remaining_person_count,
        }

    rebuilt_face_index = _empty_index()
    for face_id in kept_face_ids:
        rebuilt_face_index.add_with_ids(
            embedding_row(torch.tensor(face_vs.reconstruct(int(face_id)), dtype=torch.float32)),
            np.array([int(face_id)], dtype=np.int64),
        )

    face_vs = rebuilt_face_index
    face_meta_data = next_face_meta_data

    if kept_face_ids:
        finalize_face_clusters()
    else:
        _reset_person_store_in_memory()

    save_face_vector_stores()

    _, current_person_meta_data = load_person_vector_store()
    remaining_person_count = sum(1 for key in current_person_meta_data if not str(key).startswith("_"))
    return {
        "removed_face_ids": removed_face_ids,
        "removed_face_count": len(removed_face_ids),
        "remaining_face_count": len(kept_face_ids),
        "remaining_person_count": remaining_person_count,
    }

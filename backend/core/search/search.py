from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image

from backend.core.models.faces.detector import crop_faces, detect_faces
from backend.core.models.faces.embedding import embed_faces
from backend.core.models.faces.store import load_face_vector_store, load_person_vector_store
from backend.core.models.vision_language.base import BaseEmbeddingModel
from backend.core.models.vision_language.store import load_image_vector_store
from backend.utils.vector_store_utils import embedding_row


def _validate_top_k(top_k: int) -> int:
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")
    return int(top_k)


def _validate_page_number(page_number: int) -> int:
    if page_number <= 0:
        raise ValueError("page_number must be greater than 0")
    return int(page_number)


def _normalize_similarity(score: float) -> float:
    """Map cosine-style similarity from [-1, 1] into a clamped [0, 1] score."""
    return max(0.0, min(1.0, (float(score) + 1.0) / 2.0))


def _parse_created_at(value: str | None) -> datetime | None:
    """Parse common metadata date formats into a datetime for filtering."""
    
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    candidates = (
        text,
        text.replace(" ", "T", 1),
        text.replace(":", "-", 2).replace(" ", "T", 1),
    )

    for candidate in candidates:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue

    return None


def _normalize_face_presence(face_presence: str) -> str:
    """Normalize and validate the requested face-presence filter mode."""
    normalized = str(face_presence).strip().lower().replace(" ", "_")
    if normalized not in {"any", "contains_faces", "no_faces"}:
        raise ValueError("face_presence must be one of: any, contains_faces, no_faces")
    return normalized


def _normalize_folder_filters(folders: Sequence[str | Path] | str | Path | None) -> list[Path]:
    """Resolve optional folder filters into absolute Path objects."""
    if folders is None:
        return []
    if isinstance(folders, (str, Path)):
        folders = [folders]
    return [Path(folder).resolve() for folder in folders]


def _image_in_folders(image_path: str | None, folders: list[Path]) -> bool:
    """Return whether an image belongs to at least one resolved folder filter."""
    if not folders:
        return True
    if not image_path:
        return False

    resolved_image_path = Path(image_path).resolve()
    return any(
        resolved_image_path == folder or resolved_image_path.is_relative_to(folder)
        for folder in folders
    )


def _normalize_person_filters(person_filters: dict | Sequence[dict] | None) -> dict[str, set[int]]:
    """Convert incoming person filters into must/prefer/exclude id sets.

    The API accepts either a compact mapping of person_id to preference or a
    list of objects. Normalizing both shapes here keeps the ranking loop focused
    on set operations instead of request payload details.
    """
    normalized = {
        "must_include": set(),
        "prefer": set(),
        "exclude": set(),
    }

    if person_filters is None:
        return normalized

    if isinstance(person_filters, dict):
        items = [{"person_id": person_id, "preference": preference} for person_id, preference in person_filters.items()]
    else:
        items = list(person_filters)

    for item in items:
        if not isinstance(item, dict):
            raise TypeError("person_filters must be a dict or a sequence of dicts")

        person_id = item.get("person_id", item.get("id"))
        preference = item.get("preference", item.get("face_preference", item.get("person_preference")))

        if person_id is None or preference is None:
            raise ValueError("Each person filter must include person_id and preference")

        preference_key = str(preference).strip().lower().replace(" ", "_")
        if preference_key not in normalized:
            raise ValueError("person filter preferences must be: must_include, prefer, or exclude")

        normalized[preference_key].add(int(person_id))

    return normalized


def _build_image_face_context(face_meta_data: dict) -> tuple[set[str], dict[str, set[int]]]:
    """Build quick lookup tables for image face presence and person membership."""
    images_with_faces: set[str] = set()
    image_path_2_person_ids: dict[str, set[int]] = {}

    for key, meta_entry in face_meta_data.items():
        if str(key).startswith("_"):
            continue

        image_path = meta_entry.get("image_path")
        if not image_path:
            continue

        images_with_faces.add(image_path)
        person_id = meta_entry.get("person_id")
        if person_id is not None:
            image_path_2_person_ids.setdefault(image_path, set()).add(int(person_id))

    return images_with_faces, image_path_2_person_ids


def _collect_face_photo_scores(face_results: list[dict]) -> dict[str, float]:
    """Keep the best normalized face-match score found for each image path."""
    image_path_2_score: dict[str, float] = {}

    for face_result in face_results:
        matches = face_result.get("matches", [])

        for match in matches:
            image_path = match.get("image_path")
            if not image_path:
                continue

            normalized_score = _normalize_similarity(match.get("score", 0.0))
            current_score = image_path_2_score.get(image_path, float("-inf"))
            image_path_2_score[image_path] = max(current_score, normalized_score)

    return image_path_2_score


def _collect_image_matches(scores: np.ndarray, ids: np.ndarray, image_vs_meta_data: dict) -> list[dict]:
    """Combine FAISS image search scores and ids with stored image metadata."""
    matches = []
    for score, item_id in zip(scores[0], ids[0]):
        item_id = int(item_id)
        if item_id < 0:
            continue

        meta_entry = image_vs_meta_data.get(str(item_id), {})
        matches.append(
            {
                "image_id": item_id,
                "score": float(score),
                "image_path": meta_entry.get("image_path"),
                "created_at": meta_entry.get("created_at"),
            }
        )
    return matches


def _collect_face_matches(scores: np.ndarray, ids: np.ndarray, face_meta_data: dict) -> list[dict]:
    """Combine FAISS face search scores and ids with stored face metadata."""
    matches = []
    for score, face_id in zip(scores[0], ids[0]):
        face_id = int(face_id)
        if face_id < 0:
            continue

        meta_entry = face_meta_data.get(str(face_id), {})
        matches.append(
            {
                "face_id": face_id,
                "score": float(score),
                "person_id": meta_entry.get("person_id"),
                "image_path": meta_entry.get("image_path"),
                "created_at": meta_entry.get("created_at"),
                "face_box": meta_entry.get("face_box"),
            }
        )
    return matches


def search_by_text(text: str, image_model: BaseEmbeddingModel, top_k: int = 10) -> list[dict]:
    """Search indexed images by embedding a text query into the image model space."""
    if not text.strip():
        raise ValueError("text must not be empty")

    top_k = _validate_top_k(top_k)
    text_embedding = image_model.embed_text(text)
    image_vs, image_vs_meta_data = load_image_vector_store(image_model)

    if image_vs.ntotal == 0:
        return []

    k = min(top_k, int(image_vs.ntotal))
    scores, ids = image_vs.search(embedding_row(text_embedding), k=k)
    return _collect_image_matches(scores, ids, image_vs_meta_data)


def search_by_image(
    image: str | Path | Image.Image,
    image_model: BaseEmbeddingModel,
    top_k: int = 10,
) -> list[dict]:
    """Search indexed images by embedding a query image."""
    top_k = _validate_top_k(top_k)
    image_embedding = image_model.embed_image(image)
    image_vs, image_vs_meta_data = load_image_vector_store(image_model)

    if image_vs.ntotal == 0:
        return []

    k = min(top_k, int(image_vs.ntotal))
    scores, ids = image_vs.search(embedding_row(image_embedding), k=k)
    return _collect_image_matches(scores, ids, image_vs_meta_data)


def search_by_face(image_path: str | Path, top_k: int = 10) -> list[dict]:
    """Search indexed faces for each detected face in the query image.

    A single query image can contain multiple faces, so the return value is a
    list of per-query-face result groups. Each group preserves the detected box
    and includes the closest indexed faces from the face vector store.
    """
    top_k = _validate_top_k(top_k)
    query_path = Path(image_path)
    if not query_path.is_file():
        raise FileNotFoundError(f"Image not found: {query_path}")

    path_2_boxes = detect_faces([query_path])
    boxes = path_2_boxes.get(query_path)
    if boxes is None or len(boxes) == 0:
        return []

    path_2_crops = crop_faces({query_path: boxes})
    path_2_embeddings = embed_faces(path_2_crops, batch_size=len(path_2_crops[query_path]))
    query_embeddings = path_2_embeddings.get(query_path)
    if query_embeddings is None or query_embeddings.numel() == 0:
        return []

    face_vs, face_meta_data = load_face_vector_store()
    if face_vs.ntotal == 0:
        return []

    results = []

    for face_index, embedding in enumerate(query_embeddings):
        row = embedding_row(embedding)
        result = {
            "query_image_path": str(query_path),
            "query_face_index": face_index,
            "query_face_box": boxes[face_index].xyxy[0].tolist(),
            "match_type": "face",
            "matches": [],
        }

        face_k = min(top_k, int(face_vs.ntotal))
        face_scores, face_ids = face_vs.search(row, k=face_k)
        result["matches"] = _collect_face_matches(face_scores, face_ids, face_meta_data)

        results.append(result)

    return results


def search_by_person_id(person_id: int) -> dict:
    """Return public metadata for one indexed person."""
    person_id = int(person_id)
    _, person_meta_data = load_person_vector_store()
    person_entry = person_meta_data.get(str(person_id))
    if person_entry is None:
        raise KeyError(f"Person id not found: {person_id}")

    return {
        key: value
        for key, value in person_entry.items()
        if key != "centroid" and not str(key).startswith("_")
    }


def global_search(
    query: str,
    image_model: BaseEmbeddingModel,
    *,
    k: int = 100,
    page_number: int = 1,
    folders: Sequence[str | Path] | str | Path | None = None,
    date_cutoff: str | None = None,
    face_presence: str = "any",
    person_filters: dict | Sequence[dict] | None = None,
    face_photo_path: str | Path | None = None,
) -> dict:
    """Run combined text, folder, date, face, and person-aware search.

    Text queries search the full image vector store and use those scores as the
    initial candidate order. When no text is provided, all indexed images become
    candidates so face-photo/person filters can still work. Each candidate is
    filtered by folder, date, face presence, must-include people, and excluded
    people; remaining candidates are ranked by the average of available text,
    face-photo, and preferred-person score components, then paginated.
    """
    normalized_query = query.strip()
    if not normalized_query and face_photo_path is None:
        raise ValueError("query must not be empty unless a face photo search is provided")

    page_size = _validate_top_k(k)
    page_number = _validate_page_number(page_number)
    normalized_face_presence = _normalize_face_presence(face_presence)
    normalized_person_filters = _normalize_person_filters(person_filters)
    folder_filters = _normalize_folder_filters(folders)
    cutoff_datetime = _parse_created_at(date_cutoff)
    if date_cutoff is not None and cutoff_datetime is None:
        raise ValueError("date_cutoff must be a valid ISO-like datetime or date string")

    text_scores: np.ndarray | None = None
    image_ids: np.ndarray | None = None
    image_vs = None
    image_vs_meta_data: dict = {}

    if normalized_query:
        text_embedding = image_model.embed_text(normalized_query)
        image_vs, image_vs_meta_data = load_image_vector_store(image_model)
    else:
        image_vs, image_vs_meta_data = load_image_vector_store(image_model)

    if image_vs.ntotal == 0:
        return {
            "query": normalized_query,
            "page_number": page_number,
            "page_size": page_size,
            "total_results": 0,
            "total_pages": 0,
            "results": [],
        }

    all_image_count = int(image_vs.ntotal)
    if normalized_query:
        text_scores, image_ids = image_vs.search(embedding_row(text_embedding), k=all_image_count)
        candidate_rows = zip(text_scores[0], image_ids[0])
    else:
        candidate_rows = (
            (0.0, image_id)
            for image_id in sorted(
                int(key)
                for key in image_vs_meta_data.keys()
                if not str(key).startswith("_")
            )
        )

    _, face_meta_data = load_face_vector_store()
    images_with_faces, image_path_2_person_ids = _build_image_face_context(face_meta_data)

    face_photo_scores: dict[str, float] = {}
    if face_photo_path is not None:
        face_search_k = max(int(len(face_meta_data)), 1)
        face_results = search_by_face(face_photo_path, top_k=face_search_k)
        face_photo_scores = _collect_face_photo_scores(face_results)

    must_include_ids = normalized_person_filters["must_include"]
    prefer_ids = normalized_person_filters["prefer"]
    exclude_ids = normalized_person_filters["exclude"]

    ranked_results = []

    for raw_text_score, image_id in candidate_rows:
        image_id = int(image_id)
        if image_id < 0:
            continue

        meta_entry = image_vs_meta_data.get(str(image_id), {})
        image_path = meta_entry.get("image_path")
        created_at = meta_entry.get("created_at")
        image_person_ids = image_path_2_person_ids.get(image_path, set())
        has_faces = image_path in images_with_faces

        if not _image_in_folders(image_path, folder_filters):
            continue

        if normalized_face_presence == "contains_faces" and not has_faces:
            continue
        if normalized_face_presence == "no_faces" and has_faces:
            continue

        if cutoff_datetime is not None:
            image_datetime = _parse_created_at(created_at)
            if image_datetime is None or image_datetime < cutoff_datetime:
                continue

        if must_include_ids and not must_include_ids.issubset(image_person_ids):
            continue
        if exclude_ids and image_person_ids.intersection(exclude_ids):
            continue

        text_score = _normalize_similarity(raw_text_score) if normalized_query else None
        face_score = face_photo_scores.get(image_path, 0.0) if face_photo_path is not None else None
        preferred_people_score = (
            len(image_person_ids.intersection(prefer_ids)) / len(prefer_ids)
            if prefer_ids
            else None
        )

        score_components = []
        if text_score is not None:
            score_components.append(text_score)
        if face_score is not None:
            score_components.append(face_score)
        if preferred_people_score is not None:
            score_components.append(preferred_people_score)

        if face_photo_path is not None and face_score is not None and face_score <= 0:
            continue
        if not score_components:
            continue

        final_score = sum(score_components) / len(score_components)
        ranked_results.append(
            {
                "image_id": image_id,
                "image_path": image_path,
                "created_at": created_at,
                "final_score": final_score,
                "text_score": text_score,
                "face_score": face_score,
                "preferred_people_score": preferred_people_score,
                "has_faces": has_faces,
                "person_ids": sorted(image_person_ids),
            }
        )

    ranked_results.sort(
        key=lambda result: (
            result["final_score"],
            result["text_score"] if result["text_score"] is not None else -1.0,
            result["face_score"] if result["face_score"] is not None else -1.0,
        ),
        reverse=True,
    )

    total_results = len(ranked_results)
    total_pages = (total_results + page_size - 1) // page_size if total_results else 0
    start_index = (page_number - 1) * page_size
    end_index = start_index + page_size

    return {
        "query": normalized_query,
        "page_number": page_number,
        "page_size": page_size,
        "face_presence": normalized_face_presence,
        "total_results": total_results,
        "total_pages": total_pages,
        "results": ranked_results[start_index:end_index],
    }

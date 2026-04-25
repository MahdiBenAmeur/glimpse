from __future__ import annotations

from datetime import date, datetime, timedelta
import mimetypes
from pathlib import Path
import tempfile
from typing import Any, Literal
import uuid

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.config import FACE_QUERY_UPLOAD_DIR
from backend.core.models.faces.store import load_face_vector_store, load_person_vector_store
from backend.core.search.search import global_search, search_by_image
from backend.api.index import get_active_model_id, get_active_model_info, get_embedding_model
from backend.services.media_service import ensure_thumbnail, get_image_dimensions, get_image_taken_at
from backend.services.collection_service import CollectionService
from backend.services.library_state_service import get_image_state, load_image_meta_data
from backend.db_models.database import Session as DBSession, engine

router = APIRouter(prefix="/search", tags=["search"])


class PersonFilterInput(BaseModel):
    id: int
    preference: Literal["must_include", "prefer", "exclude", "Must include", "Prefer", "Exclude"] = "must_include"


class SearchRequest(BaseModel):
    query: str
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=50, ge=1, le=200)
    folders: list[str] = Field(default_factory=list)
    dateRange: Literal["any", "today", "last-7-days", "last-30-days", "this-year"] = "any"
    facePresence: Literal["any", "faces", "no-faces"] = "any"
    people: list[PersonFilterInput] = Field(default_factory=list)
    facePhotoPath: str | None = None
    modelId: str | None = None


class SearchImageResult(BaseModel):
    id: str
    imageId: int
    url: str
    thumbnailUrl: str | None = None
    path: str | None = None
    filename: str
    folder: str
    dateTaken: str | None = None
    width: int | None = None
    height: int | None = None
    isFavorite: bool = False
    faceCount: int = 0
    people: list[str] = Field(default_factory=list)
    collections: list[str] = Field(default_factory=list)
    score: float | None = None


class FacePhotoUploadResponse(BaseModel):
    path: str
    filename: str


class SearchResponse(BaseModel):
    query: str
    page: int
    pageSize: int
    totalResults: int
    totalPages: int
    activeModelId: str | None = None
    activeModel: dict[str, Any] | None = None
    results: list[SearchImageResult]


def _load_image_meta_data() -> dict[str, Any]:
    return load_image_meta_data()


def _normalize_person_preference(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _resolve_date_cutoff(date_range: str) -> str | None:
    today = date.today()
    if date_range == "any":
        return None
    if date_range == "today":
        return datetime.combine(today, datetime.min.time()).isoformat()
    if date_range == "last-7-days":
        return datetime.combine(today - timedelta(days=7), datetime.min.time()).isoformat()
    if date_range == "last-30-days":
        return datetime.combine(today - timedelta(days=30), datetime.min.time()).isoformat()
    if date_range == "this-year":
        return datetime(today.year, 1, 1).isoformat()
    raise HTTPException(status_code=400, detail=f"Unsupported dateRange: {date_range}")


def _normalize_face_presence(value: str) -> str:
    if value == "faces":
        return "contains_faces"
    if value == "no-faces":
        return "no_faces"
    return "any"


def _build_people_lookup() -> dict[int, str]:
    _, person_meta_data = load_person_vector_store()
    lookup: dict[int, str] = {}
    for key, entry in person_meta_data.items():
        if str(key).startswith("_"):
            continue
        person_id = int(key)
        lookup[person_id] = entry.get("name") or f"Person {person_id}"
    return lookup


def _build_collection_lookup() -> dict[int, str]:
    with DBSession(engine) as session:
        return {
            int(collection.id): collection.name
            for collection in CollectionService.get_all(session=session, skip=0, limit=1000)
        }


def _build_image_people_map() -> dict[str, set[int]]:
    _, face_meta_data = load_face_vector_store()
    image_people: dict[str, set[int]] = {}
    for key, value in face_meta_data.items():
        if str(key).startswith("_"):
            continue
        image_path = value.get("image_path")
        person_id = value.get("person_id")
        if image_path is None or person_id is None:
            continue
        image_people.setdefault(str(image_path), set()).add(int(person_id))
    return image_people


def _build_image_url(_request: Request, image_id: int) -> str:
    return f"/api/search/images/{image_id}/file"


def _build_thumbnail_url(_request: Request, image_id: int) -> str:
    return f"/api/search/images/{image_id}/thumbnail"


def _build_search_result_item(
    *,
    request: Request,
    image_id: int,
    image_path: Path,
    created_at: str | None,
    face_count: int,
    person_names: list[str],
    collection_lookup: dict[int, str],
    score: float | None,
) -> dict[str, Any]:
    width, height = get_image_dimensions(image_path)
    image_state = get_image_state(image_id)
    date_taken = get_image_taken_at(image_path, created_at)
    return {
        "id": str(image_id),
        "imageId": image_id,
        "url": _build_image_url(request, image_id),
        "thumbnailUrl": _build_thumbnail_url(request, image_id),
        "path": str(image_path),
        "filename": image_path.name,
        "folder": str(image_path.parent),
        "dateTaken": date_taken,
        "width": width,
        "height": height,
        "isFavorite": bool(image_state.get("is_favorite", False)),
        "faceCount": face_count,
        "people": person_names,
        "collections": [
            collection_lookup.get(int(collection_id), f"Collection {collection_id}")
            for collection_id in image_state.get("collection_ids", [])
        ],
        "score": score,
    }


@router.post("/", response_model=SearchResponse)
def run_search(payload: SearchRequest, request: Request) -> dict[str, Any]:
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    try:
        image_model = get_embedding_model(payload.modelId)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    person_filters = [
        {"person_id": item.id, "preference": _normalize_person_preference(item.preference)}
        for item in payload.people
    ]

    try:
        raw_results = global_search(
            payload.query,
            image_model,
            k=payload.pageSize,
            page_number=payload.page,
            folders=payload.folders or None,
            date_cutoff=_resolve_date_cutoff(payload.dateRange),
            face_presence=_normalize_face_presence(payload.facePresence),
            person_filters=person_filters or None,
            face_photo_path=payload.facePhotoPath,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        print(exc)
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc

    people_lookup = _build_people_lookup()
    image_people_map = _build_image_people_map()
    collection_lookup = _build_collection_lookup()

    items: list[dict[str, Any]] = []
    for result in raw_results.get("results", []):
        image_path_value = result.get("image_path")
        if not image_path_value:
            continue

        image_path = Path(image_path_value)
        person_ids = sorted(image_people_map.get(str(image_path), set()))
        person_names = [people_lookup.get(person_id, f"Person {person_id}") for person_id in person_ids]
        items.append(
            _build_search_result_item(
                request=request,
                image_id=int(result["image_id"]),
                image_path=image_path,
                created_at=result.get("created_at"),
                face_count=len(person_ids),
                person_names=person_names,
                collection_lookup=collection_lookup,
                score=result.get("final_score"),
            )
        )

    return {
        "query": raw_results.get("query", payload.query),
        "page": raw_results.get("page_number", payload.page),
        "pageSize": raw_results.get("page_size", payload.pageSize),
        "totalResults": raw_results.get("total_results", len(items)),
        "totalPages": raw_results.get("total_pages", 0),
        "activeModelId": payload.modelId or get_active_model_id(),
        "activeModel": get_active_model_info(),
        "results": items,
    }


@router.post("/face-photo", response_model=FacePhotoUploadResponse)
async def upload_face_photo(file: UploadFile = File(...)) -> dict[str, str]:
    filename = file.filename or "face-photo.jpg"
    suffix = Path(filename).suffix or ".jpg"
    if file.content_type is not None and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")

    FACE_QUERY_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target_path = FACE_QUERY_UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    try:
        with target_path.open("wb") as handle:
            handle.write(await file.read())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not save face photo: {exc}") from exc
    finally:
        await file.close()

    return {
        "path": str(target_path.resolve()),
        "filename": filename,
    }


@router.get("/images/{image_id}/file", name="read_search_image_file")
def read_search_image_file(image_id: int) -> FileResponse:
    meta_data = _load_image_meta_data()
    image_entry = meta_data.get(str(image_id))
    if image_entry is None:
        raise HTTPException(status_code=404, detail="Image not found in the index")

    image_path = Path(image_entry.get("image_path", ""))
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=404, detail="Indexed image file is missing")

    media_type, _ = mimetypes.guess_type(str(image_path))
    return FileResponse(path=image_path, filename=image_path.name, media_type=media_type or "application/octet-stream")


@router.get("/images/{image_id}/thumbnail", name="read_search_image_thumbnail")
def read_search_image_thumbnail(image_id: int) -> FileResponse:
    meta_data = _load_image_meta_data()
    image_entry = meta_data.get(str(image_id))
    if image_entry is None:
        raise HTTPException(status_code=404, detail="Image not found in the index")

    image_path = Path(image_entry.get("image_path", ""))
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=404, detail="Indexed image file is missing")

    try:
        thumbnail_path = ensure_thumbnail(image_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not build thumbnail: {exc}") from exc

    return FileResponse(path=thumbnail_path, filename=thumbnail_path.name, media_type="image/jpeg")


@router.get("/similar/{image_id}", response_model=list[SearchImageResult])
def find_similar_images(image_id: int, request: Request, limit: int = 12) -> list[dict[str, Any]]:
    meta_data = _load_image_meta_data()
    image_entry = meta_data.get(str(image_id))
    if image_entry is None:
        raise HTTPException(status_code=404, detail="Image not found in the index")

    image_path = Path(image_entry.get("image_path", ""))
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=404, detail="Indexed image file is missing")

    try:
        image_model = get_embedding_model()
        matches = search_by_image(image_path, image_model, top_k=limit + 1)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Similarity search failed: {exc}") from exc

    people_lookup = _build_people_lookup()
    image_people_map = _build_image_people_map()
    collection_lookup = _build_collection_lookup()
    items: list[dict[str, Any]] = []

    for match in matches:
        matched_id = int(match["image_id"])
        if matched_id == image_id:
            continue
        matched_path = Path(match.get("image_path", ""))
        if not matched_path.exists():
            continue
        person_ids = sorted(image_people_map.get(str(matched_path), set()))
        person_names = [people_lookup.get(person_id, f"Person {person_id}") for person_id in person_ids]
        items.append(
            _build_search_result_item(
                request=request,
                image_id=matched_id,
                image_path=matched_path,
                created_at=match.get("created_at"),
                face_count=len(person_ids),
                person_names=person_names,
                collection_lookup=collection_lookup,
                score=match.get("score"),
            )
        )
        if len(items) >= limit:
            break

    return items


@router.post("/by-image", response_model=list[SearchImageResult])
async def find_similar_images_by_upload(request: Request, file: UploadFile = File(...), limit: int = 24) -> list[dict[str, Any]]:
    active_model_id = get_active_model_id()
    if active_model_id is None:
        raise HTTPException(status_code=400, detail="Select a model before running image similarity search")

    suffix = Path(file.filename or "query-image.jpg").suffix or ".jpg"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(await file.read())
            temp_path = Path(temp_file.name)

        image_model = get_embedding_model(active_model_id)
        matches = search_by_image(temp_path, image_model, top_k=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Similarity search failed: {exc}") from exc
    finally:
        await file.close()
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass

    people_lookup = _build_people_lookup()
    image_people_map = _build_image_people_map()
    collection_lookup = _build_collection_lookup()
    items: list[dict[str, Any]] = []

    for match in matches:
        matched_id = int(match["image_id"])
        matched_path = Path(match.get("image_path", ""))
        if not matched_path.exists():
            continue
        person_ids = sorted(image_people_map.get(str(matched_path), set()))
        person_names = [people_lookup.get(person_id, f"Person {person_id}") for person_id in person_ids]
        items.append(
            _build_search_result_item(
                request=request,
                image_id=matched_id,
                image_path=matched_path,
                created_at=match.get("created_at"),
                face_count=len(person_ids),
                person_names=person_names,
                collection_lookup=collection_lookup,
                score=match.get("score"),
            )
        )
        if len(items) >= limit:
            break

    return items

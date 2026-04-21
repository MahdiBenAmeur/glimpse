import io
from pathlib import Path
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from backend.db_models.database import get_session
from backend.core.models.faces.store import load_person_vector_store, save_face_vector_stores
from backend.services.media_service import get_image_dimensions, get_image_taken_at
from backend.services.library_state_service import find_image_id_by_path, get_image_state
from backend.services.person_service import PersonService
from backend.schemas.person import PersonCreate, PersonUpdate, PersonRead

router = APIRouter(prefix="/people", tags=["people"])


def _build_person_response(person_id: int, entry: dict[str, Any], request: Request) -> dict[str, Any]:
    image_paths = entry.get("image_paths", [])
    image_created_ats = [value for value in entry.get("image_created_ats", []) if value]
    last_seen = max(image_created_ats) if image_created_ats else None
    return {
        "id": person_id,
        "name": entry.get("name"),
        "faceUrl": str(request.url_for("read_person_face", person_id=person_id)),
        "imageCount": int(entry.get("count", len(image_paths))),
        "lastSeen": last_seen,
    }

@router.post("/", response_model=PersonRead)
def create_person(person_in: PersonCreate, session: Session = Depends(get_session)):
    return PersonService.create(session=session, person_in=person_in)

@router.get("/")
def read_people(request: Request, skip: int = 0, limit: int | None = None):
    _, person_meta_data = load_person_vector_store()
    people: list[dict[str, Any]] = []
    for key, entry in person_meta_data.items():
        if str(key).startswith("_") or not isinstance(entry, dict):
            continue
        people.append(_build_person_response(int(key), entry, request))
    # Keep named people first so renaming a person makes them easier to find,
    # and avoid silently dropping them behind a low default page size.
    people.sort(
        key=lambda item: (
            0 if item["name"] else 1,
            (item["name"] or "").lower(),
            -item["imageCount"],
            item["id"],
        )
    )
    return people[skip:] if limit is None else people[skip : skip + limit]

@router.get("/{person_id}")
def read_person(person_id: int, request: Request):
    _, person_meta_data = load_person_vector_store()
    entry = person_meta_data.get(str(person_id))
    if not isinstance(entry, dict):
        raise HTTPException(status_code=404, detail="Person not found")
    return _build_person_response(person_id, entry, request)

@router.get("/{person_id}/images")
def read_person_images(person_id: int, request: Request):
    _, person_meta_data = load_person_vector_store()
    entry = person_meta_data.get(str(person_id))
    if not isinstance(entry, dict):
        raise HTTPException(status_code=404, detail="Person not found")

    image_paths = entry.get("image_paths", [])
    image_created_ats = entry.get("image_created_ats", [])
    items = []
    for index, image_path in enumerate(image_paths):
        image_id = find_image_id_by_path(image_path)
        if image_id is None:
            continue
        path = Path(image_path)
        state = get_image_state(image_id)
        width, height = get_image_dimensions(path)
        date_taken = get_image_taken_at(path, image_created_ats[index] if index < len(image_created_ats) else None)
        items.append(
            {
                "id": str(image_id),
                "imageId": image_id,
                "url": f"/api/search/images/{image_id}/file",
                "thumbnailUrl": f"/api/search/images/{image_id}/thumbnail",
                "path": str(path),
                "filename": path.name,
                "folder": str(path.parent),
                "dateTaken": date_taken,
                "width": width,
                "height": height,
                "isFavorite": bool(state.get("is_favorite", False)),
                "faceCount": 1,
                "people": [entry.get("name") or f"Person {person_id}"],
                "collections": [str(collection_id) for collection_id in state.get("collection_ids", [])],
            }
        )
    return items

@router.get("/{person_id}/face", name="read_person_face")
def read_person_face(person_id: int):
    _, person_meta_data = load_person_vector_store()
    entry = person_meta_data.get(str(person_id))
    if not isinstance(entry, dict):
        raise HTTPException(status_code=404, detail="Person not found")

    image_paths = entry.get("image_paths", [])
    face_boxes = entry.get("face_boxes", [])
    quality_scores = entry.get("quality_scores", [])
    if not image_paths:
        raise HTTPException(status_code=404, detail="Face image not available")

    best_index = 0
    if quality_scores:
        best_index = max(range(len(quality_scores)), key=lambda index: float(quality_scores[index]))

    image_path = Path(image_paths[best_index if best_index < len(image_paths) else 0])
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Face source image not found")

    try:
        from PIL import Image

        with Image.open(image_path) as image:
            image = image.convert("RGB")
            if face_boxes:
                face_box = face_boxes[best_index] if best_index < len(face_boxes) else face_boxes[0]
                left, top, right, bottom = [int(value) for value in face_box]
                image = image.crop((left, top, right, bottom))
            output = io.BytesIO()
            image.save(output, format="JPEG")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not render face image: {exc}") from exc

    output.seek(0)
    return StreamingResponse(output, media_type="image/jpeg")

@router.patch("/{person_id}")
def update_person(person_id: int, person_in: PersonUpdate):
    _, person_meta_data = load_person_vector_store()
    entry = person_meta_data.get(str(person_id))
    if not isinstance(entry, dict):
        raise HTTPException(status_code=404, detail="Person not found")
    update_data = person_in.model_dump(exclude_unset=True)
    if "name" in update_data:
        entry["name"] = update_data["name"]
        save_face_vector_stores()
    return {
        "id": person_id,
        "name": entry.get("name"),
    }

@router.delete("/{person_id}")
def delete_person(person_id: int, session: Session = Depends(get_session)):
    success = PersonService.delete(session=session, person_id=person_id)
    if not success:
        raise HTTPException(status_code=404, detail="Person not found")
    return {"ok": True}

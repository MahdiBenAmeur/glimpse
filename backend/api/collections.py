from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pathlib import Path
from sqlmodel import Session
from typing import List
from pydantic import BaseModel

from backend.db_models.database import get_session
from backend.services.import_service import pick_image_paths
from backend.services.library_state_service import add_image_to_collection, clear_collection, find_image_id_by_path, get_collection_image_ids, get_image_state, get_indexed_image, remove_image_from_collection
from backend.services.media_service import get_image_dimensions, get_image_taken_at
from backend.services.collection_service import CollectionService
from backend.schemas.collection import CollectionCreate, CollectionUpdate, CollectionRead

router = APIRouter(prefix="/collections", tags=["collections"])


class CollectionSummaryResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    imageCount: int
    previewUrls: list[str]
    modifiedDate: str | None = None


def _build_collection_response(collection, request: Request) -> dict:
    image_ids = get_collection_image_ids(int(collection.id))
    preview_urls = [
        f"/api/search/images/{image_id}/thumbnail"
        for image_id in image_ids[:4]
        if get_indexed_image(image_id) is not None
    ]
    modified_date = collection.modified_date.isoformat() if collection.modified_date is not None else None
    return {
        "id": int(collection.id),
        "name": collection.name,
        "description": collection.description,
        "imageCount": len(image_ids),
        "previewUrls": preview_urls,
        "modifiedDate": modified_date,
    }


def _sync_collection_metadata(session: Session, collection_id: int):
    collection = CollectionService.get(session=session, collection_id=collection_id)
    if collection is None:
        return None
    collection.image_count = len(get_collection_image_ids(collection_id))
    collection.modified_date = datetime.utcnow()
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return collection

@router.post("/", response_model=CollectionRead)
def create_collection(collection_in: CollectionCreate, session: Session = Depends(get_session)):
    return CollectionService.create(session=session, collection_in=collection_in)

@router.get("/", response_model=List[CollectionSummaryResponse])
def read_collections(request: Request, skip: int = 0, limit: int = 100, session: Session = Depends(get_session)):
    collections = CollectionService.get_all(session=session, skip=skip, limit=limit)
    return [_build_collection_response(collection, request) for collection in collections]

@router.get("/{collection_id}", response_model=CollectionSummaryResponse)
def read_collection(collection_id: int, request: Request, session: Session = Depends(get_session)):
    collection = CollectionService.get(session=session, collection_id=collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return _build_collection_response(collection, request)

@router.patch("/{collection_id}", response_model=CollectionRead)
def update_collection(collection_id: int, collection_in: CollectionUpdate, session: Session = Depends(get_session)):
    collection = CollectionService.update(session=session, collection_id=collection_id, collection_in=collection_in)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection

@router.delete("/{collection_id}")
def delete_collection(collection_id: int, session: Session = Depends(get_session)):
    success = CollectionService.delete(session=session, collection_id=collection_id)
    if not success:
        raise HTTPException(status_code=404, detail="Collection not found")
    clear_collection(collection_id)
    return {"ok": True}


@router.get("/{collection_id}/images")
def read_collection_images(collection_id: int, request: Request):
    image_ids = get_collection_image_ids(collection_id)
    items = []
    for image_id in image_ids:
        image_entry = get_indexed_image(image_id)
        if image_entry is None:
            continue
        state = get_image_state(image_id)
        width, height = get_image_dimensions(image_entry["image_path"])
        date_taken = get_image_taken_at(image_entry["image_path"], image_entry.get("created_at"))
        items.append(
            {
                "id": str(image_id),
                "imageId": image_id,
                "url": f"/api/search/images/{image_id}/file",
                "thumbnailUrl": f"/api/search/images/{image_id}/thumbnail",
                "path": image_entry["image_path"],
                "filename": Path(image_entry["image_path"]).name,
                "folder": str(Path(image_entry["image_path"]).parent),
                "dateTaken": date_taken,
                "width": width,
                "height": height,
                "isFavorite": bool(state.get("is_favorite", False)),
                "faceCount": 0,
                "people": [],
                "collections": [str(collection_id) for collection_id in state.get("collection_ids", [])],
            }
        )
    return items


@router.post("/{collection_id}/images")
def add_collection_images(collection_id: int, payload: dict, session: Session = Depends(get_session)):
    if CollectionService.get(session=session, collection_id=collection_id) is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    image_ids = [int(image_id) for image_id in payload.get("imageIds", [])]
    for image_id in image_ids:
        add_image_to_collection(image_id, collection_id)
    _sync_collection_metadata(session, collection_id)
    return {"ok": True, "collectionId": collection_id, "imageCount": len(get_collection_image_ids(collection_id))}


@router.post("/{collection_id}/pick-images")
def pick_collection_images(collection_id: int, session: Session = Depends(get_session)):
    collection = CollectionService.get(session=session, collection_id=collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    selected_paths = pick_image_paths()
    if not selected_paths:
        raise HTTPException(status_code=400, detail="Image selection was cancelled")

    added_ids: list[int] = []
    skipped_paths: list[str] = []
    auto_indexed_count = 0
    for selected_path in selected_paths:
        image_id = find_image_id_by_path(selected_path)
        if image_id is None:
            from backend.api.index import get_active_model_id, get_embedding_model
            from backend.core.indexing.index import index_batch

            active_model_id = get_active_model_id()
            if active_model_id is None:
                skipped_paths.append(str(selected_path))
                continue

            image_model = get_embedding_model(active_model_id)
            batch_stats = index_batch([selected_path], image_model, batch_size=1, save_after_batch=True)
            indexed_ids = [int(image_id) for image_id in batch_stats.get("image_indexing", {}).get("indexed_ids", [])]
            if not indexed_ids:
                skipped_paths.append(str(selected_path))
                continue
            image_id = indexed_ids[0]
            auto_indexed_count += 1
        add_image_to_collection(image_id, collection_id)
        added_ids.append(image_id)

    if not added_ids and skipped_paths:
        raise HTTPException(status_code=400, detail="Selected photos could not be added")

    _sync_collection_metadata(session, collection_id)

    return {
        "ok": True,
        "collectionId": collection_id,
        "addedCount": len(set(added_ids)),
        "autoIndexedCount": auto_indexed_count,
        "skippedPaths": skipped_paths,
        "imageCount": len(get_collection_image_ids(collection_id)),
    }


@router.delete("/{collection_id}/images/{image_id}")
def delete_collection_image(collection_id: int, image_id: int, session: Session = Depends(get_session)):
    if CollectionService.get(session=session, collection_id=collection_id) is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    remove_image_from_collection(image_id, collection_id)
    _sync_collection_metadata(session, collection_id)
    return {"ok": True}

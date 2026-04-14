from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from backend.db_models.database import get_session
from backend.services.media_service import get_image_dimensions, get_image_taken_at
from backend.services.image_service import ImageService
from backend.services.library_state_service import get_collection_image_ids, get_image_state, get_indexed_image, list_indexed_images, set_image_favorite
from backend.schemas.image import ImageCreate, ImageUpdate, ImageRead

router = APIRouter(prefix="/images", tags=["images"])


def _build_image_url(request: Request, image_id: int) -> str:
    return f"/api/search/images/{image_id}/file"


def _build_thumbnail_url(request: Request, image_id: int) -> str:
    return f"/api/search/images/{image_id}/thumbnail"


def _build_indexed_image_response(image_id: int, image_path: str | Path, created_at: str | None, request: Request) -> dict[str, Any]:
    path = Path(image_path)
    state = get_image_state(image_id)
    width, height = get_image_dimensions(path)
    date_taken = get_image_taken_at(path, created_at)

    return {
        "id": str(image_id),
        "imageId": image_id,
        "url": _build_image_url(request, image_id),
        "thumbnailUrl": _build_thumbnail_url(request, image_id),
        "filename": path.name,
        "folder": str(path.parent),
        "path": str(path),
        "dateTaken": date_taken,
        "width": width,
        "height": height,
        "isFavorite": bool(state.get("is_favorite", False)),
        "faceCount": 0,
        "people": [],
        "collections": [str(collection_id) for collection_id in state.get("collection_ids", [])],
    }

@router.post("/", response_model=ImageRead)
def create_image(image_in: ImageCreate, session: Session = Depends(get_session)):
    return ImageService.create(session=session, image_in=image_in)

@router.get("/", response_model=List[ImageRead])
def read_images(skip: int = 0, limit: int = 100, session: Session = Depends(get_session)):
    return ImageService.get_all(session=session, skip=skip, limit=limit)


@router.get("/indexed")
def read_indexed_images(request: Request, favorite: bool = False, skip: int = 0, limit: int = 100):
    items = list_indexed_images()
    if favorite:
        items = [item for item in items if get_image_state(int(item["image_id"])).get("is_favorite", False)]
    sliced = items[skip : skip + limit]
    return [
        _build_indexed_image_response(
            int(item["image_id"]),
            item["image_path"],
            item.get("created_at"),
            request,
        )
        for item in sliced
    ]


@router.get("/indexed/{image_id}")
def read_indexed_image(image_id: int, request: Request):
    item = get_indexed_image(image_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Indexed image not found")
    return _build_indexed_image_response(image_id, item["image_path"], item.get("created_at"), request)


@router.patch("/indexed/{image_id}/favorite")
def update_indexed_image_favorite(image_id: int, payload: dict[str, bool]):
    if "isFavorite" not in payload:
        raise HTTPException(status_code=400, detail="isFavorite is required")
    item = get_indexed_image(image_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Indexed image not found")
    state = set_image_favorite(image_id, bool(payload["isFavorite"]))
    return {
        "ok": True,
        "imageId": image_id,
        "isFavorite": bool(state.get("is_favorite", False)),
        "updatedAt": datetime.utcnow().isoformat(),
    }


@router.post("/indexed/{image_id}/open-external")
def open_indexed_image_externally(image_id: int):
    item = get_indexed_image(image_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Indexed image not found")

    image_path = Path(item["image_path"])
    if not image_path.exists() or not image_path.is_file():
        raise HTTPException(status_code=404, detail="Indexed image file is missing")

    try:
        if os.name == "nt":
            os.startfile(str(image_path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(image_path)])
        else:
            subprocess.Popen(["xdg-open", str(image_path)])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not open image externally: {exc}") from exc

    return {"ok": True, "imageId": image_id, "path": str(image_path)}

@router.get("/{image_id}", response_model=ImageRead)
def read_image(image_id: int, session: Session = Depends(get_session)):
    image = ImageService.get(session=session, image_id=image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return image

@router.patch("/{image_id}", response_model=ImageRead)
def update_image(image_id: int, image_in: ImageUpdate, session: Session = Depends(get_session)):
    image = ImageService.update(session=session, image_id=image_id, image_in=image_in)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    return image

@router.delete("/{image_id}")
def delete_image(image_id: int, session: Session = Depends(get_session)):
    success = ImageService.delete(session=session, image_id=image_id)
    if not success:
        raise HTTPException(status_code=404, detail="Image not found")
    return {"ok": True}

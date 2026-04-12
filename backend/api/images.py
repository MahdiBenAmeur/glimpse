from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List

from backend.db_models.database import get_session
from backend.services.image_service import ImageService
from backend.schemas.image import ImageCreate, ImageUpdate, ImageRead

router = APIRouter(prefix="/images", tags=["images"])

@router.post("/", response_model=ImageRead)
def create_image(image_in: ImageCreate, session: Session = Depends(get_session)):
    return ImageService.create(session=session, image_in=image_in)

@router.get("/", response_model=List[ImageRead])
def read_images(skip: int = 0, limit: int = 100, session: Session = Depends(get_session)):
    return ImageService.get_all(session=session, skip=skip, limit=limit)

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

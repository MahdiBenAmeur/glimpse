from sqlmodel import Session, select
from backend.db_models.image import Image
from backend.schemas.image import ImageCreate, ImageUpdate
from typing import List, Optional

class ImageService:
    @staticmethod
    def create(session: Session, image_in: ImageCreate) -> Image:
        image = Image.model_validate(image_in)
        session.add(image)
        session.commit()
        session.refresh(image)
        return image

    @staticmethod
    def get(session: Session, image_id: int) -> Optional[Image]:
        return session.get(Image, image_id)

    @staticmethod
    def get_all(session: Session, skip: int = 0, limit: int = 100) -> List[Image]:
        return session.exec(select(Image).offset(skip).limit(limit)).all()

    @staticmethod
    def update(session: Session, image_id: int, image_in: ImageUpdate) -> Optional[Image]:
        db_image = session.get(Image, image_id)
        if not db_image:
            return None
        update_data = image_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_image, key, value)
        session.add(db_image)
        session.commit()
        session.refresh(db_image)
        return db_image

    @staticmethod
    def delete(session: Session, image_id: int) -> bool:
        db_image = session.get(Image, image_id)
        if not db_image:
            return False
        session.delete(db_image)
        session.commit()
        return True

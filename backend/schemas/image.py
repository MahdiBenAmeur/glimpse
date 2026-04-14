from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ImageBase(BaseModel):
    url: str
    filename: str
    folder_id: Optional[int] = None
    date_taken: Optional[datetime] = None
    width: Optional[int] = None
    height: Optional[int] = None
    is_favorite: bool = False
    face_count: int = 0

class ImageCreate(ImageBase):
    pass

class ImageUpdate(BaseModel):
    url: Optional[str] = None
    filename: Optional[str] = None
    folder_id: Optional[int] = None
    date_taken: Optional[datetime] = None
    width: Optional[int] = None
    height: Optional[int] = None
    is_favorite: Optional[bool] = None
    face_count: Optional[int] = None

class ImageRead(ImageBase):
    id: int
    class Config:
        from_attributes = True

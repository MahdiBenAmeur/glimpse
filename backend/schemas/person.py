from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PersonBase(BaseModel):
    name: Optional[str] = None
    face_url: str
    image_count: int = 0
    last_seen: Optional[datetime] = None

class PersonCreate(PersonBase):
    id: str

class PersonUpdate(BaseModel):
    name: Optional[str] = None
    face_url: Optional[str] = None
    image_count: Optional[int] = None
    last_seen: Optional[datetime] = None

class PersonRead(PersonBase):
    id: str
    class Config:
        from_attributes = True

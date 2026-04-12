from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CollectionBase(BaseModel):
    name: str
    description: Optional[str] = None
    image_count: int = 0
    modified_date: Optional[datetime] = None

class CollectionCreate(CollectionBase):
    id: str

class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_count: Optional[int] = None
    modified_date: Optional[datetime] = None

class CollectionRead(CollectionBase):
    id: str
    class Config:
        from_attributes = True

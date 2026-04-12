from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from .links import ImageCollectionLink

class Collection(SQLModel, table=True):
    __tablename__ = "collections"
    id: str = Field(primary_key=True)
    name: str
    description: Optional[str] = None
    image_count: int = Field(default=0)
    modified_date: Optional[datetime] = None

    images: List["Image"] = Relationship(back_populates="collections", link_model=ImageCollectionLink)

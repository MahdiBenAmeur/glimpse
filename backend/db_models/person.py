from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from .links import ImagePeopleLink

class Person(SQLModel, table=True):
    __tablename__ = "people"
    id: str = Field(primary_key=True)
    name: Optional[str] = None
    face_url: str
    image_count: int = Field(default=0)
    last_seen: Optional[datetime] = None

    images: List["Image"] = Relationship(back_populates="people", link_model=ImagePeopleLink)

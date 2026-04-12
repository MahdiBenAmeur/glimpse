from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from .links import ImagePeopleLink

if TYPE_CHECKING:
    from .image import Image

class Person(SQLModel, table=True):
    __tablename__ = "people"
    id: int = Field(default=None, primary_key=True)
    name: Optional[str] = None
    face_url: str
    image_count: int = Field(default=0)
    last_seen: Optional[datetime] = None

    images: List[Image] = Relationship(back_populates="people", link_model=ImagePeopleLink)

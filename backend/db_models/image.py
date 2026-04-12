from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from .links import ImagePeopleLink, ImageCollectionLink
from .folder import Folder
from .person import Person
from .collection import Collection

class Image(SQLModel, table=True):
    __tablename__ = "images"
    id: str = Field(primary_key=True)
    url: str
    filename: str
    folder_id: Optional[str] = Field(default=None, foreign_key="folders.id")
    date_taken: Optional[datetime] = None
    width: Optional[int] = None
    height: Optional[int] = None
    is_favorite: bool = Field(default=False)
    face_count: int = Field(default=0)

    folder: Optional[Folder] = Relationship(back_populates="images")
    people: List[Person] = Relationship(back_populates="images", link_model=ImagePeopleLink)
    collections: List[Collection] = Relationship(back_populates="images", link_model=ImageCollectionLink)

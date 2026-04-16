from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from .links import ImageCollectionLink

if TYPE_CHECKING:
    from .image import Image

class Collection(SQLModel, table=True):
    __tablename__ = "collections"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    image_count: int = Field(default=0)
    modified_date: Optional[datetime] = Field(default_factory=datetime.now)

    images: List[Image] = Relationship(back_populates="collections", link_model=ImageCollectionLink)

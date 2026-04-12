from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from .image import Image
    
class Folder(SQLModel, table=True):
    __tablename__ = "folders"
    id: Optional[int] = Field(default=None, primary_key=True)
    path: str= Field(unique=True)
    image_count: int = Field(default=0)
    last_scan_time: Optional[datetime] = None
    status: Optional[str] = None
    include_subfolders: bool = Field(default=False)

    images: List[Image] = Relationship(back_populates="folder")

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class Folder(SQLModel, table=True):
    __tablename__ = "folders"
    id: str = Field(primary_key=True)
    path: str
    image_count: int = Field(default=0)
    last_scan_time: Optional[datetime] = None
    status: Optional[str] = None
    include_subfolders: bool = Field(default=True)

    images: List["Image"] = Relationship(back_populates="folder")

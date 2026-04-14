from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Image(SQLModel, table=True):
    __tablename__ = "images"
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str
    filename: str
    folder_id: Optional[int] = Field(default=None, foreign_key="folders.id")
    date_taken: Optional[datetime] = None
    width: Optional[int] = None
    height: Optional[int] = None
    is_favorite: bool = Field(default=False)
    face_count: int = Field(default=0)

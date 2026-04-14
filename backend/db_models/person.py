from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Person(SQLModel, table=True):
    __tablename__ = "people"
    id: int = Field(default=None, primary_key=True)
    name: Optional[str] = None
    face_url: str
    image_count: int = Field(default=0)
    last_seen: Optional[datetime] = None

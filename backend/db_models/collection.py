from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Collection(SQLModel, table=True):
    __tablename__ = "collections"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    image_count: int = Field(default=0)
    modified_date: Optional[datetime] = None

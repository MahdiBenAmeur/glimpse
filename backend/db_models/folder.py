from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
    
class Folder(SQLModel, table=True):
    __tablename__ = "folders"
    id: Optional[int] = Field(default=None, primary_key=True)
    path: str= Field(unique=True)
    image_count: int = Field(default=0)
    last_scan_time: Optional[datetime] = None
    status: Optional[str] = None
    include_subfolders: bool = Field(default=False)

from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FolderBase(BaseModel):
    path: str
    image_count: int = 0
    last_scan_time: Optional[datetime] = None
    status: Optional[str] = None
    include_subfolders: bool = True

class FolderCreate(FolderBase):
    id: str

class FolderUpdate(BaseModel):
    path: Optional[str] = None
    image_count: Optional[int] = None
    last_scan_time: Optional[datetime] = None
    status: Optional[str] = None
    include_subfolders: Optional[bool] = None

class FolderRead(FolderBase):
    id: str
    class Config:
        from_attributes = True

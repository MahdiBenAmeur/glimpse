from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class SavedSearchBase(BaseModel):
    name: str
    query: Optional[str] = ""
    filters: Dict[str, Any] = Field(default_factory=dict)
    last_used: Optional[datetime] = None

class SavedSearchCreate(SavedSearchBase):
    pass

class SavedSearchUpdate(BaseModel):
    name: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    last_used: Optional[datetime] = None

class SavedSearchRead(SavedSearchBase):
    id: str

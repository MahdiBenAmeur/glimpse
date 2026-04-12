from fastapi import APIRouter, HTTPException
from typing import List

from backend.services.saved_search_service import SavedSearchService
from backend.schemas.saved_search import SavedSearchCreate, SavedSearchUpdate, SavedSearchRead


router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])


@router.post("/", response_model=SavedSearchRead)
def create_saved_search(search_in: SavedSearchCreate):
    """Create a new saved search (stored in JSON)."""
    return SavedSearchService.create(search_in=search_in)


@router.get("/", response_model=List[SavedSearchRead])
def read_saved_searches(skip: int = 0, limit: int = 100):
    """Get all saved searches with basic pagination."""
    return SavedSearchService.get_all(skip=skip, limit=limit)


@router.get("/{search_id}", response_model=SavedSearchRead)
def read_saved_search(search_id: str):
    """Get a specific saved search by ID."""
    search = SavedSearchService.get(search_id=search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return search


@router.patch("/{search_id}", response_model=SavedSearchRead)
def update_saved_search(search_id: str, search_in: SavedSearchUpdate):
    """Update fields on an existing saved search."""
    search = SavedSearchService.update(search_id=search_id, search_in=search_in)
    if not search:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return search


@router.delete("/{search_id}")
def delete_saved_search(search_id: str):
    """Delete a saved search."""
    success = SavedSearchService.delete(search_id=search_id)
    if not success:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return {"ok": True}

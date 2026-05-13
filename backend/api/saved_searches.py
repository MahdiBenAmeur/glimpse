from fastapi import APIRouter, HTTPException

from backend.schemas.saved_search import SavedSearchCreate, SavedSearchRead, SavedSearchUpdate
from backend.services.saved_search_service import SavedSearchService

router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])


@router.get("/", response_model=list[SavedSearchRead])
def read_saved_searches(skip: int = 0, limit: int = 100):
    """
    Lists all saved search queries.
    """
    return SavedSearchService.get_all(skip=skip, limit=limit)


@router.post("/", response_model=SavedSearchRead)
def create_saved_search(search_in: SavedSearchCreate):
    """
    Saves a new search query.
    """
    return SavedSearchService.create(search_in)


@router.get("/{search_id}", response_model=SavedSearchRead)
def read_saved_search(search_id: str):
    """
    Retrieves a specific saved search.
    """
    saved_search = SavedSearchService.get(search_id)
    if not saved_search:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return saved_search


@router.patch("/{search_id}", response_model=SavedSearchRead)
def update_saved_search(search_id: str, search_in: SavedSearchUpdate):
    """
    Updates an existing saved search.
    """
    saved_search = SavedSearchService.update(search_id, search_in)
    if not saved_search:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return saved_search


@router.delete("/{search_id}")
def delete_saved_search(search_id: str):
    """
    Removes a saved search.
    """
    success = SavedSearchService.delete(search_id)
    if not success:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return {"ok": True}

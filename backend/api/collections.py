from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List

from backend.db_models.database import get_session
from backend.services.collection_service import CollectionService
from backend.schemas.collection import CollectionCreate, CollectionUpdate, CollectionRead

router = APIRouter(prefix="/collections", tags=["collections"])

@router.post("/", response_model=CollectionRead)
def create_collection(collection_in: CollectionCreate, session: Session = Depends(get_session)):
    return CollectionService.create(session=session, collection_in=collection_in)

@router.get("/", response_model=List[CollectionRead])
def read_collections(skip: int = 0, limit: int = 100, session: Session = Depends(get_session)):
    return CollectionService.get_all(session=session, skip=skip, limit=limit)

@router.get("/{collection_id}", response_model=CollectionRead)
def read_collection(collection_id: str, session: Session = Depends(get_session)):
    collection = CollectionService.get(session=session, collection_id=collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection

@router.patch("/{collection_id}", response_model=CollectionRead)
def update_collection(collection_id: str, collection_in: CollectionUpdate, session: Session = Depends(get_session)):
    collection = CollectionService.update(session=session, collection_id=collection_id, collection_in=collection_in)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection

@router.delete("/{collection_id}")
def delete_collection(collection_id: str, session: Session = Depends(get_session)):
    success = CollectionService.delete(session=session, collection_id=collection_id)
    if not success:
        raise HTTPException(status_code=404, detail="Collection not found")
    return {"ok": True}

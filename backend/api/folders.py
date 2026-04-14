from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List

from backend.db_models.database import get_session
from backend.services.folder_service import FolderService
from backend.schemas.folder import FolderCreate, FolderUpdate, FolderRead

router = APIRouter(prefix="/folders", tags=["folders"])

@router.post("/", response_model=FolderRead)
def create_folder(folder_in: FolderCreate, session: Session = Depends(get_session)):
    return FolderService.create(session=session, folder_in=folder_in)

@router.get("/", response_model=List[FolderRead])
def read_folders(skip: int = 0, limit: int = 100, session: Session = Depends(get_session)):
    return FolderService.get_all(session=session, skip=skip, limit=limit)

@router.get("/{folder_id}", response_model=FolderRead)
def read_folder(folder_id: int, session: Session = Depends(get_session)):
    folder = FolderService.get(session=session, folder_id=folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder

@router.patch("/{folder_id}", response_model=FolderRead)
def update_folder(folder_id: int, folder_in: FolderUpdate, session: Session = Depends(get_session)):
    folder = FolderService.update(session=session, folder_id=folder_id, folder_in=folder_in)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder

@router.delete("/{folder_id}")
def delete_folder(folder_id: int, session: Session = Depends(get_session)):
    success = FolderService.delete(session=session, folder_id=folder_id)
    if not success:
        raise HTTPException(status_code=404, detail="Folder not found")
    return {"ok": True}

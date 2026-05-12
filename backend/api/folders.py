from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from backend.db_models.database import get_session
from backend.db_models.folder import Folder
from backend.services.folder_service import FolderService
from backend.services.import_service import import_image_files, pick_folder_path, pick_image_paths
from backend.schemas.folder import FolderCreate, FolderUpdate, FolderRead

router = APIRouter(prefix="/folders", tags=["folders"])


class PickFolderRequest(BaseModel):
    includeSubfolders: bool = True


class ImportImagesResponse(BaseModel):
    folder: FolderRead
    importedCount: int
    files: list[str]


def _get_or_create_folder_record(session: Session, *, path: str, include_subfolders: bool) -> Folder:
    """
    Ensures a database record exists for a given file system path.
    """
    return FolderService.create(
        session=session,
        folder_in=FolderCreate(
            path=path,
            image_count=0,
            status="ready",
            include_subfolders=include_subfolders,
        ),
    )


@router.post("/", response_model=FolderRead)
def create_folder(folder_in: FolderCreate, session: Session = Depends(get_session)):
    """
    Creates a new folder record in the database.
    """
    return FolderService.create(session=session, folder_in=folder_in)

@router.get("/", response_model=List[FolderRead])
def read_folders(skip: int = 0, limit: int = 100, session: Session = Depends(get_session)):
    """
    Lists all registered folders.
    """
    return FolderService.get_all(session=session, skip=skip, limit=limit)

@router.get("/{folder_id}", response_model=FolderRead)
def read_folder(folder_id: int, session: Session = Depends(get_session)):
    """
    Retrieves details for a specific folder.
    """
    folder = FolderService.get(session=session, folder_id=folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder

@router.patch("/{folder_id}", response_model=FolderRead)
def update_folder(folder_id: int, folder_in: FolderUpdate, session: Session = Depends(get_session)):
    """
    Updates folder configuration.
    """
    folder = FolderService.update(session=session, folder_id=folder_id, folder_in=folder_in)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    return folder

@router.delete("/{folder_id}")
def delete_folder(folder_id: int, session: Session = Depends(get_session)):
    """
    Removes a folder record from the database.
    """
    success = FolderService.delete(session=session, folder_id=folder_id)
    if not success:
        raise HTTPException(status_code=404, detail="Folder not found")
    return {"ok": True}


@router.post("/pick", response_model=FolderRead)
def pick_folder(payload: PickFolderRequest, session: Session = Depends(get_session)):
    """
    Opens a folder picker and registers the selected path.
    """
    selected_path = pick_folder_path()
    if not selected_path:
        raise HTTPException(status_code=400, detail="Folder selection was cancelled")

    return _get_or_create_folder_record(
        session,
        path=str(selected_path),
        include_subfolders=payload.includeSubfolders,
    )


@router.post("/import-images", response_model=ImportImagesResponse)
def import_images(session: Session = Depends(get_session)):
    """
    Opens a file picker to import and index specific image files.
    """
    selected_paths = pick_image_paths()
    if not selected_paths:
        raise HTTPException(status_code=400, detail="Image selection was cancelled")

    try:
        imported = import_image_files(selected_paths)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    folder = _get_or_create_folder_record(
        session,
        path=str(imported["folder_path"]),
        include_subfolders=False,
    )
    return {
        "folder": folder,
        "importedCount": int(imported["imported_count"]),
        "files": imported["files"],
    }

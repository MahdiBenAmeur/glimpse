from sqlmodel import Session, select
from backend.db_models.folder import Folder
from backend.schemas.folder import FolderCreate, FolderUpdate
from typing import List, Optional, Sequence
from pathlib import Path
from backend.core.models.faces.store import purge_face_entries
from backend.core.models.vision_language.store import purge_image_entries
from backend.services.library_state_service import remove_image_states
from backend.utils.path_utils import canonicalize_path, canonicalize_path_key


def _folder_score(folder: Folder) -> tuple[int, int, int]:
    """
    Calculates a priority score for a folder.
    """
    return (
        int(folder.image_count or 0),
        1 if folder.last_scan_time is not None else 0,
        int(folder.id or 0),
    )


def _dedupe_visible_folders(folders: Sequence[Folder]) -> list[Folder]:
    """
    Removes duplicate folder records by path.
    """
    best_by_key: dict[str, Folder] = {}
    for folder in folders:
        key = canonicalize_path_key(folder.path)
        existing = best_by_key.get(key)
        folder.path = canonicalize_path(folder.path)
        if existing is None:
            best_by_key[key] = folder
        elif _folder_score(folder) > _folder_score(existing):
            best_by_key[key] = folder
    return sorted(best_by_key.values(), key=lambda folder: int(folder.id or 0))


def _find_matching_folders(session: Session, path: str) -> list[Folder]:
    """
    Finds all database records matching a path.
    """
    target_key = canonicalize_path_key(path)
    matches = [
        folder
        for folder in session.exec(select(Folder)).all()
        if canonicalize_path_key(folder.path) == target_key
    ]
    for folder in matches:
        folder.path = canonicalize_path(folder.path)
    return matches


def _find_existing_folder(session: Session, path: str) -> Folder | None:
    """
    Finds the best existing record for a path.
    """
    matches = _find_matching_folders(session, path)
    if not matches:
        return None
    best_match = max(matches, key=_folder_score)
    return best_match


def _path_is_within_folder(image_path: str, folder_path: str) -> bool:
    """
    Checks if a file path is inside a folder.
    """
    resolved_image_path = Path(canonicalize_path(image_path))
    resolved_folder_path = Path(canonicalize_path(folder_path))
    try:
        resolved_image_path.relative_to(resolved_folder_path)
        return True
    except ValueError:
        return False


def _purge_indexed_folder_data(folder_path: str) -> None:
    """
    Removes indexed data for all images in a folder.
    """
    def matches_folder(image_path: str) -> bool:
        return _path_is_within_folder(image_path, folder_path)

    image_purge = purge_image_entries(folder_path)
    remove_image_states(image_purge.get("removed_ids", []))
    purge_face_entries(matches_folder)


def _collapse_duplicate_folders(session: Session, keep_folder: Folder, *, path: str) -> None:
    """
    Deletes redundant folder records.
    """
    duplicates = [
        folder
        for folder in _find_matching_folders(session, path)
        if int(folder.id or 0) != int(keep_folder.id or 0)
    ]
    if not duplicates:
        return
    for duplicate in duplicates:
        session.delete(duplicate)
    session.add(keep_folder)
    session.commit()
    session.refresh(keep_folder)

class FolderService:
    @staticmethod
    def create(session: Session, folder_in: FolderCreate) -> Folder:
        """
        Registers a new folder or updates an existing one.
        """
        payload = folder_in.model_dump()
        payload["path"] = canonicalize_path(payload["path"])
        existing = _find_existing_folder(session, payload["path"])
        if existing is not None:
            existing.include_subfolders = payload.get("include_subfolders", existing.include_subfolders)
            existing.status = payload.get("status", existing.status)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            _collapse_duplicate_folders(session, existing, path=payload["path"])
            return existing
        folder = Folder.model_validate(payload)
        session.add(folder)
        session.commit()
        session.refresh(folder)
        return folder

    @staticmethod
    def get(session: Session, folder_id: int) -> Optional[Folder]:
        """
        Retrieves a folder by ID.
        """
        return session.get(Folder, folder_id)

    @staticmethod
    def get_all(session: Session, skip: int = 0, limit: int = 100) -> List[Folder]:
        """
        Lists unique folders.
        """
        folders = session.exec(select(Folder)).all()
        visible = _dedupe_visible_folders(folders)
        return visible[skip : skip + limit]

    @staticmethod
    def update(session: Session, folder_id: int, folder_in: FolderUpdate) -> Optional[Folder]:
        """
        Updates folder configuration.
        """
        db_folder = session.get(Folder, folder_id)
        if not db_folder:
            return None
        update_data = folder_in.model_dump(exclude_unset=True)
        if "path" in update_data and update_data["path"] is not None:
            update_data["path"] = canonicalize_path(update_data["path"])
        for key, value in update_data.items():
            setattr(db_folder, key, value)
        session.add(db_folder)
        session.commit()
        session.refresh(db_folder)
        return db_folder

    @staticmethod
    def delete(session: Session, folder_id: int) -> bool:
        """
        Removes a folder and its indexed data.
        """
        db_folder = session.get(Folder, folder_id)
        if not db_folder:
            return False
        _purge_indexed_folder_data(db_folder.path)
        for folder in _find_matching_folders(session, db_folder.path):
            session.delete(folder)
        session.commit()
        return True

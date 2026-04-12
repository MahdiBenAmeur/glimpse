from sqlmodel import Session, select
from backend.db_models.folder import Folder
from backend.schemas.folder import FolderCreate, FolderUpdate
from typing import List, Optional

class FolderService:
    @staticmethod
    def create(session: Session, folder_in: FolderCreate) -> Folder:
        folder = Folder.model_validate(folder_in)
        session.add(folder)
        session.commit()
        session.refresh(folder)
        return folder

    @staticmethod
    def get(session: Session, folder_id: str) -> Optional[Folder]:
        return session.get(Folder, folder_id)

    @staticmethod
    def get_all(session: Session, skip: int = 0, limit: int = 100) -> List[Folder]:
        return session.exec(select(Folder).offset(skip).limit(limit)).all()

    @staticmethod
    def update(session: Session, folder_id: str, folder_in: FolderUpdate) -> Optional[Folder]:
        db_folder = session.get(Folder, folder_id)
        if not db_folder:
            return None
        update_data = folder_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_folder, key, value)
        session.add(db_folder)
        session.commit()
        session.refresh(db_folder)
        return db_folder

    @staticmethod
    def delete(session: Session, folder_id: str) -> bool:
        db_folder = session.get(Folder, folder_id)
        if not db_folder:
            return False
        session.delete(db_folder)
        session.commit()
        return True

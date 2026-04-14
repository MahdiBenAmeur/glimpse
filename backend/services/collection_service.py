from sqlmodel import Session, select
from backend.db_models.collection import Collection
from backend.schemas.collection import CollectionCreate, CollectionUpdate
from typing import List, Optional

class CollectionService:
    @staticmethod
    def create(session: Session, collection_in: CollectionCreate) -> Collection:
        collection = Collection.model_validate(collection_in)
        session.add(collection)
        session.commit()
        session.refresh(collection)
        return collection

    @staticmethod
    def get(session: Session, collection_id: int) -> Optional[Collection]:
        return session.get(Collection, collection_id)

    @staticmethod
    def get_all(session: Session, skip: int = 0, limit: int = 100) -> List[Collection]:
        return session.exec(select(Collection).offset(skip).limit(limit)).all()

    @staticmethod
    def update(session: Session, collection_id: int, collection_in: CollectionUpdate) -> Optional[Collection]:
        db_collection = session.get(Collection, collection_id)
        if not db_collection:
            return None
        db_data = db_collection.model_dump()
        update_data = collection_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_collection, key, value)
        session.add(db_collection)
        session.commit()
        session.refresh(db_collection)
        return db_collection

    @staticmethod
    def delete(session: Session, collection_id: int) -> bool:
        db_collection = session.get(Collection, collection_id)
        if not db_collection:
            return False
        session.delete(db_collection)
        session.commit()
        return True

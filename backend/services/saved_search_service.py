import json
import uuid
from typing import List, Optional
from backend.schemas.saved_search import SavedSearchCreate, SavedSearchUpdate, SavedSearchRead
from backend.config import SAVED_SEARCHES_PATH


class SavedSearchService:
    @staticmethod
    def _read_data() -> List[dict]:
        if not SAVED_SEARCHES_PATH.exists():
            return []
        try:
            with SAVED_SEARCHES_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

    @staticmethod
    def _write_data(data: List[dict]):
        SAVED_SEARCHES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SAVED_SEARCHES_PATH.open("w", encoding="utf-8") as f:
            # We use default=str so datetime gets serialized correctly
            json.dump(data, f, indent=4, default=str)

    @staticmethod
    def create(search_in: SavedSearchCreate) -> SavedSearchRead:
        data = SavedSearchService._read_data()
        
        search_id = str(uuid.uuid4())
        
        new_search = search_in.model_dump()
        new_search["id"] = search_id
        
        # Convert datetime to string early for json storage if needed,
        # but model_dump() usually keeps it as datetime object which gets caught by default=str
        
        data.append(new_search)
        SavedSearchService._write_data(data)
        
        return SavedSearchRead(**new_search)

    @staticmethod
    def get(search_id: str) -> Optional[SavedSearchRead]:
        data = SavedSearchService._read_data()
        for item in data:
            if item.get("id") == search_id:
                return SavedSearchRead(**item)
        return None

    @staticmethod
    def get_all(skip: int = 0, limit: int = 100) -> List[SavedSearchRead]:
        data = SavedSearchService._read_data()
        paginated_data = data[skip : skip + limit]
        return [SavedSearchRead(**item) for item in paginated_data]

    @staticmethod
    def update(search_id: str, search_in: SavedSearchUpdate) -> Optional[SavedSearchRead]:
        data = SavedSearchService._read_data()
        for i, item in enumerate(data):
            if item.get("id") == search_id:
                update_data = search_in.model_dump(exclude_unset=True)
                for key, value in update_data.items():
                    item[key] = value
                
                data[i] = item
                SavedSearchService._write_data(data)
                return SavedSearchRead(**item)
        return None

    @staticmethod
    def delete(search_id: str) -> bool:
        data = SavedSearchService._read_data()
        initial_length = len(data)
        
        filtered_data = [item for item in data if item.get("id") != search_id]
        
        if len(filtered_data) < initial_length:
            SavedSearchService._write_data(filtered_data)
            return True
            
        return False

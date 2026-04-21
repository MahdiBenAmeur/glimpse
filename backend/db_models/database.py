from sqlmodel import SQLModel, create_engine, Session
from typing import Generator
import os
from backend.db_models import Folder, Person, Collection, Image

# Determine the absolute path to the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sqlite_file_name = os.path.join(BASE_DIR, "glimpse.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}

engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)

def create_db_and_tables() -> None:
    """
    Creates the necessary tables in the SQLite database.
    """
    SQLModel.metadata.create_all(engine, checkfirst=True)

def get_session() -> Generator[Session, None, None]:
    """
    Provides a database session for querying, automatically handling cleanup.
    Usage example in FastAPI: `session: Session = Depends(get_session)`
    """
    with Session(engine) as session:
        yield session

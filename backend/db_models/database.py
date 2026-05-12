from sqlmodel import SQLModel, create_engine, Session
from typing import Generator
from backend.db_models import Folder, Person, Collection, Image
from backend.config import SQLITE_DB_PATH

SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
sqlite_url = f"sqlite:///{SQLITE_DB_PATH.as_posix()}"

connect_args = {"check_same_thread": False}

engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)

def create_db_and_tables() -> None:
    """
    Creates the necessary tables in the SQLite database.
    """
    SQLModel.metadata.create_all(engine, checkfirst=True)

def get_session() -> Generator[Session, None, None]:
    """
    Provides a database session.
    """
    with Session(engine) as session:
        yield session

from sqlmodel import Session, select
from backend.db_models.person import Person
from backend.schemas.person import PersonCreate, PersonUpdate
from typing import List, Optional

class PersonService:
    @staticmethod
    def create(session: Session, person_in: PersonCreate) -> Person:
        """
        Creates a new person record.
        """
        person = Person.model_validate(person_in)
        session.add(person)
        session.commit()
        session.refresh(person)
        return person

    @staticmethod
    def get(session: Session, person_id: int) -> Optional[Person]:
        """
        Retrieves a person by ID.
        """
        return session.get(Person, person_id)

    @staticmethod
    def get_all(session: Session, skip: int = 0, limit: int = 100) -> List[Person]:
        """
        Lists person records.
        """
        return session.exec(select(Person).offset(skip).limit(limit)).all()

    @staticmethod
    def update(session: Session, person_id: int, person_in: PersonUpdate) -> Optional[Person]:
        """
        Updates a person record.
        """
        db_person = session.get(Person, person_id)
        if not db_person:
            return None
        update_data = person_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_person, key, value)
        session.add(db_person)
        session.commit()
        session.refresh(db_person)
        return db_person

    @staticmethod
    def delete(session: Session, person_id: int) -> bool:
        """
        Deletes a person record.
        """
        db_person = session.get(Person, person_id)
        if not db_person:
            return False
        session.delete(db_person)
        session.commit()
        return True

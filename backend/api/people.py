from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List

from backend.db_models.database import get_session
from backend.services.person_service import PersonService
from backend.schemas.person import PersonCreate, PersonUpdate, PersonRead

router = APIRouter(prefix="/people", tags=["people"])

@router.post("/", response_model=PersonRead)
def create_person(person_in: PersonCreate, session: Session = Depends(get_session)):
    return PersonService.create(session=session, person_in=person_in)

@router.get("/", response_model=List[PersonRead])
def read_people(skip: int = 0, limit: int = 100, session: Session = Depends(get_session)):
    return PersonService.get_all(session=session, skip=skip, limit=limit)

@router.get("/{person_id}", response_model=PersonRead)
def read_person(person_id: str, session: Session = Depends(get_session)):
    person = PersonService.get(session=session, person_id=person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person

@router.patch("/{person_id}", response_model=PersonRead)
def update_person(person_id: str, person_in: PersonUpdate, session: Session = Depends(get_session)):
    person = PersonService.update(session=session, person_id=person_id, person_in=person_in)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person

@router.delete("/{person_id}")
def delete_person(person_id: str, session: Session = Depends(get_session)):
    success = PersonService.delete(session=session, person_id=person_id)
    if not success:
        raise HTTPException(status_code=404, detail="Person not found")
    return {"ok": True}

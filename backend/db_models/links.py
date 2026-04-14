from sqlmodel import SQLModel, Field

class ImagePeopleLink(SQLModel, table=True):
    __tablename__ = "image_people"
    image_id: int = Field(foreign_key="images.id", primary_key=True)
    person_id: int = Field(foreign_key="people.id", primary_key=True)

class ImageCollectionLink(SQLModel, table=True):
    __tablename__ = "image_collections"
    image_id: int = Field(foreign_key="images.id", primary_key=True)
    collection_id: int = Field(foreign_key="collections.id", primary_key=True)

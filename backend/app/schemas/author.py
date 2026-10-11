from datetime import date

from pydantic import Field

from app.schemas.common import ORMModel


class AuthorOut(ORMModel):
    author_id: str = Field(validation_alias="external_author_id")
    name: str
    email: str
    phone: str | None = None
    city: str | None = None
    joined_date: date | None = None


class AuthorRef(ORMModel):
    author_id: str = Field(validation_alias="external_author_id")
    name: str

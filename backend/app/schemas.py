import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class HolidayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # lets Pydantic read from the ORM object

    id: int
    name: str
    description: str | None
    date: dt.date
    country_code: str
    primary_type: str
    types: list[str]
    nationwide: bool
    locations: str | None
    states: list[str]   # comes from the Holiday.states property, not a column
    url: str | None


class HolidayPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[HolidayOut]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

class UserOut(BaseModel):                       # NO password field, so it can never leak
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
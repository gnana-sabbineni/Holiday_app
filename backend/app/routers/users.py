from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm   # needs: pip install python-multipart
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import Token, UserCreate, UserOut
from ..security import CurrentUser, create_access_token, hash_password, verify_password

router = APIRouter(prefix="/user", tags=["users"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: UserCreate, db: DbSession):
    exists = db.scalar(
        select(User.id).where(or_(User.email == body.email, User.username == body.username))
    )
    if exists:
        raise HTTPException(status_code=409, detail="User already exists")

    user = User(email=body.email, username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:                  # two requests raced past the check above
        db.rollback()
        raise HTTPException(status_code=409, detail="User already exists")
    return user                             # response_model=UserOut strips everything but id/username/email


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    # OAuth2 spec: the field is always called "username". We put the EMAIL in it.
    user = db.scalar(select(User).where(User.email == form.username))
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",     # same message for both cases
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token({"sub": user.email}))


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser):
    return current_user
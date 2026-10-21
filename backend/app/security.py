import datetime as dt
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from sqlalchemy import select

from .config import ACCESS_TOKEN_MINUTES, JWT_ALGORITHM, SECRET_KEY
from .database import get_db
from .models import User

_hasher = PasswordHash.recommended()                  # Argon2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="user/login")


def hash_password(password: str) -> str:
    return _hasher.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return _hasher.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: dt.timedelta | None = None) -> str:
    expire = dt.datetime.now(dt.timezone.utc) + (expires_delta or dt.timedelta(minutes=ACCESS_TOKEN_MINUTES))
    return jwt.encode({**data, "exp": expire}, SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(                                  # plain def, not async
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:                             # bad signature, expired, malformed
        raise credentials_exception
    email = payload.get("sub")
    if email is None:
        raise credentials_exception
    user = db.scalar(select(User).where(User.email == email))
    if user is None:                                   # token valid but user was deleted
        raise credentials_exception
    return user                                        # the ORM object itself


CurrentUser = Annotated[User, Depends(get_current_user)]   # reusable shortcut
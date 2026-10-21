import os

from dotenv import load_dotenv

load_dotenv()  # reads backend/.env into environment variables


def require(name: str) -> str:
    """Return a required setting, or stop with a clear message if it's missing."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing setting '{name}'. Add it to backend/.env")
    return value


DATABASE_URL = require("DATABASE_URL")      # required now: no silent fallback to a SQLite file
SECRET_KEY = require("SECRET_KEY")          # signs login tokens
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]
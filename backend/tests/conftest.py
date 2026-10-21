import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (importing registers User/Holiday tables on Base.metadata)
from app.database import Base, get_db
from app.main import app

from .common_methods import USER,REGISTER_URL,ME_URL,register,login

@pytest.fixture
def engine():
    """A brand-new, empty, in-memory SQLite database for every single test."""
    engine = create_engine(
        "sqlite://",                                  # no file name = in memory
        connect_args={"check_same_thread": False},    # FastAPI may use it from another thread
        poolclass=StaticPool,                         # keep ONE connection, so the memory DB survives
    )
    Base.metadata.create_all(engine)                  # like context.Database.EnsureCreated()
    yield engine
    engine.dispose()                                  # closing the connection destroys the DB


@pytest.fixture
def session_factory(engine):
    # same settings as your real SessionLocal
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def db_session(session_factory):
    """A session the TEST itself can use, e.g. to insert seed data directly."""
    with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory):
    """An HTTP client talking to your real app, but wired to the SQLite database."""
    def override_get_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()  # always undo the swap


@pytest.fixture
def auth_headers(client):
    register(client)
    token = login(client).json()["access_token"]
    header = {"Authorization": f"Bearer {token}"}
    yield header



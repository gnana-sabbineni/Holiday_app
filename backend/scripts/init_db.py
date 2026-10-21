from app import models  # noqa: F401  (importing registers the tables on Base)
from app.database import Base, engine

Base.metadata.create_all(engine)  # creates MISSING tables only; never alters existing ones
print("Tables:", ", ".join(Base.metadata.tables))
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    sessionmaker,
)

from backend.app.database.base import Base


load_dotenv()


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://carerelay:carerelay_dev@localhost:5433/carerelay",
)


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    expire_on_commit=False,
)


def initialize_database():
    """
    Create any CareRelay database tables that do not already exist.

    Importing the models here ensures SQLAlchemy knows about every
    mapped table before create_all() runs.
    """

    from backend.app.database import models  # noqa: F401

    Base.metadata.create_all(
        bind=engine
    )


def get_database_session():
    """
    Provide one SQLAlchemy database session and guarantee that it
    closes after use.
    """

    with SessionLocal() as session:
        yield session
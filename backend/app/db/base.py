from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

database_url = str(settings.database_url)
engine = create_engine(database_url, pool_pre_ping=True)
try:
    with engine.connect():
        pass
except OperationalError:
    fallback_url = "sqlite+pysqlite:///./edueval_ai.sqlite3"
    engine = create_engine(fallback_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

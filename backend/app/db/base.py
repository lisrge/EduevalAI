from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

database_url = str(settings.database_url)
engine = create_engine(database_url, pool_pre_ping=True)

# Ensure every connection uses utf8mb4 to handle emoji and 4-byte UTF-8
@event.listens_for(engine, "connect")
def _set_utf8mb4(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

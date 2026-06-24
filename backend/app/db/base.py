from sqlalchemy import create_engine, event
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

database_url = str(settings.database_url)


def _sqlite_fallback_url() -> str:
    sqlite_path = (settings.backend_root / "edueval_ai.sqlite3").resolve()
    return f"sqlite+pysqlite:///{sqlite_path.as_posix()}"


def _build_engine(url: str):
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def _resolve_engine():
    primary_engine = _build_engine(database_url)
    if database_url.startswith("sqlite"):
        return primary_engine, database_url, False

    try:
        with primary_engine.connect():
            pass
        return primary_engine, database_url, False
    except SQLAlchemyError as exc:
        fallback_url = _sqlite_fallback_url()
        print(
            f"[db] Failed to connect to primary database `{database_url}`. "
            f"Falling back to SQLite at `{fallback_url}`. Reason: {exc}"
        )
        fallback_engine = _build_engine(fallback_url)
        with fallback_engine.connect():
            pass
        return fallback_engine, fallback_url, True


engine, active_database_url, using_sqlite_fallback = _resolve_engine()

# Ensure every connection uses utf8mb4 to handle emoji and 4-byte UTF-8
@event.listens_for(engine, "connect")
def _set_utf8mb4(dbapi_conn, connection_record):
    if engine.dialect.name != "mysql":
        return
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
    finally:
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

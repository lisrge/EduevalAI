from app.db.base import Base, engine
from app.models.application import ApplicationRecord, ScoreResult
from app.models.user import User, UserSession


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()

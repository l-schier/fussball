from typing_extensions import Annotated
from fastapi.params import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from config import settings
from database.tables import Base, Player


engine = None


def initialize_database(engine):
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.query(Player).count()
        if session.query(Player).count() == 0:
            session.add_all(
                [
                    Player(name="player_1"),
                    Player(name="player_2"),
                    Player(name="player_3"),
                    Player(name="player_4"),
                ]
            )
            session.commit()


if settings.database_type == "postgresql":
    engine = create_engine(
        f"postgresql://{settings.user}:{settings.password}@{settings.host}:{settings.port}/{settings.database}"
    )
    # try:
    #     initialize_database(engine)
    # except Exception as e:
    #     print(f"Error initializing database: {e}")

elif settings.database_type == "sqlite":
    engine = create_engine(
        "sqlite:///data/database.db", max_overflow=30, pool_size=15, pool_recycle=600
    )


def get_session():
    with Session(engine) as session:
        return session


Connection = Annotated[Session, Depends(get_session)]

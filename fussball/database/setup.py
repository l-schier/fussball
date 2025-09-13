from typing_extensions import Annotated
from fastapi.params import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fussball.config import settings
from fussball.database.tables import Base, Player

import tempfile
import os

_tempdir = tempfile.TemporaryDirectory()

if settings.env == "dev":
    # Create a temporary directory for the app lifetime
    db_path = os.path.join(_tempdir.name, "dev.sqlite3")
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([Player(name="player_1"), Player(name="player_2"), Player(name="player_3"), Player(name="player_4")])
        session.commit()
else:
    engine = create_engine(
        f"postgresql://{settings.user}:{settings.password}@{settings.host}:{settings.port}/{settings.database}"
    )

def get_session():
    with Session(engine) as session:
        yield session


Connection = Annotated[Session, Depends(get_session)]
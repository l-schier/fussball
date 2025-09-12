from typing_extensions import Annotated
from fastapi.params import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fussball.config import settings

engine = create_engine(
    f"postgresql://{settings.user}:{settings.password}@{settings.host}:{settings.port}/{settings.database}"
)

def get_session():
    with Session(engine) as session:
        yield session


Connection = Annotated[Session, Depends(get_session)]
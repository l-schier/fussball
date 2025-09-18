from typing_extensions import Annotated
from fastapi.params import Depends
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from fussball.config import settings
from fussball.database.tables import Base, Player
import asyncio

import tempfile
import os

_tempdir = tempfile.TemporaryDirectory()
async def initialize_database(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as session:
        session.add_all([Player(name="player_1"), Player(name="player_2"), Player(name="player_3"), Player(name="player_4")])
        await session.commit()
    
if settings.env == "dev":
    # Create a temporary directory for the app lifetime
    db_path = os.path.join(_tempdir.name, "dev.sqlite3")
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", connect_args={"check_same_thread": False})
    asyncio.run(initialize_database(engine))
else:
    engine = create_engine(
        f"postgresql://{settings.user}:{settings.password}@{settings.host}:{settings.port}/{settings.database}"
    )

async def get_session():
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session(autoflush=False) as session:
        yield session


Connection = Annotated[AsyncSession, Depends(get_session)]
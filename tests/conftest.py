from __future__ import annotations

import importlib
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FUSSBALL_ROOT = PROJECT_ROOT / "fussball"
if str(FUSSBALL_ROOT) not in sys.path:
    sys.path.insert(0, str(FUSSBALL_ROOT))


@pytest.fixture
def configured_site():
    settings_module = importlib.import_module("config")
    setup_module = importlib.import_module("database.setup")
    tables_module = importlib.import_module("database.tables")
    main_module = importlib.import_module("main")

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    tables_module.Base.metadata.create_all(engine)

    player_ids = [uuid.UUID(int=index) for index in range(1, 5)]
    team_ids = [uuid.UUID(int=101), uuid.UUID(int=102)]
    match_id = uuid.UUID(int=201)
    with Session(engine) as session:
        players = [
            tables_module.Player(id=player_id, name=f"Player {index}", created_at=datetime(2024, 1, 1))
            for index, player_id in enumerate(player_ids, start=1)
        ]
        teams = [
            tables_module.Team(
                id=team_ids[0],
                team_player_1_id=player_ids[0],
                team_player_2_id=player_ids[1],
                created_at=datetime(2024, 1, 1),
            ),
            tables_module.Team(
                id=team_ids[1],
                team_player_1_id=player_ids[2],
                team_player_2_id=player_ids[3],
                created_at=datetime(2024, 1, 1),
            ),
        ]
        session.add_all(players + teams)
        session.flush()
        match = tables_module.Match(
            id=match_id,
            created_at=datetime(2024, 1, 2, 12),
            winning_team_id=team_ids[0],
            losing_team_id=team_ids[1],
            winning_team_score=5,
            losing_team_score=2,
        )
        session.add(match)
        session.flush()
        session.add_all(
            [
                tables_module.TeamMatch(
                    id=uuid.UUID(int=301), team_id=team_ids[0], match_id=match_id, created_at=datetime(2024, 1, 2, 12)
                ),
                tables_module.TeamMatch(
                    id=uuid.UUID(int=302), team_id=team_ids[1], match_id=match_id, created_at=datetime(2024, 1, 2, 12)
                ),
            ]
        )
        session.add_all(
            [
                tables_module.PlayerRating(
                    id=uuid.UUID(int=401 + index),
                    match_id=match_id,
                    player_id=player_id,
                    rating=1500 + index,
                    created_at=datetime(2024, 1, 2, 12),
                )
                for index, player_id in enumerate(player_ids)
            ]
            + [
                tables_module.TeamRating(
                    id=uuid.UUID(int=501 + index),
                    team_match_id=uuid.UUID(int=301 + index),
                    rating=1500 + index,
                    created_at=datetime(2024, 1, 2, 12),
                )
                for index in range(2)
            ]
        )
        session.commit()

    def make_app(app_settings):
        app = main_module.create_app(app_settings)

        def test_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[setup_module.get_session] = test_session
        return app

    app = make_app(
        settings_module.Settings(
            admin_username="admin",
            admin_password="correct horse battery staple",
            admin_session_secret="test-only-session-signing-secret",
            admin_session_cookie_secure=False,
        )
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, engine, tables_module, match_id, team_ids, make_app, settings_module.Settings
    engine.dispose()

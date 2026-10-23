from __future__ import annotations

import importlib
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
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


def test_administrator_can_sign_in_with_deployment_credentials(configured_site):
    client, _, _, match_id, _, *_ = configured_site

    login_page = client.get("/admin/login")
    assert login_page.status_code == 200
    assert "Administrator sign in" in login_page.text

    rejected = client.post("/admin/sign-in", json={"username": "admin", "password": "wrong"})
    assert rejected.status_code == 401

    accepted = client.post(
        "/admin/sign-in",
        json={"username": "admin", "password": "correct horse battery staple"},
    )
    assert accepted.status_code == 200
    assert accepted.headers["HX-Redirect"] == "/match"
    assert "HX-Push-Url" not in accepted.headers
    assert "Signed in as administrator" in accepted.text
    assert "fussball_admin" in client.cookies
    matches_page = client.get(accepted.headers["HX-Redirect"])
    assert matches_page.status_code == 200
    assert "Team 1 score" in matches_page.text
    assert "Edit match" in client.get(f"/match/{match_id}").text

    protected_response = client.post(f"/match/{match_id}/edit", json={"score_team_1": 8, "score_team_2": 3})
    assert protected_response.status_code == 200
    assert "Match scores updated" in protected_response.text


def test_authenticated_administrator_corrects_both_scores_without_changing_match_identity(configured_site):
    client, engine, tables, match_id, team_ids, *_ = configured_site

    public_detail = client.get(f"/match/{match_id}")
    assert public_detail.status_code == 200
    assert "Edit match" not in public_detail.text

    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    edit_page = client.get(f"/match/{match_id}/edit")
    assert edit_page.status_code == 200
    assert "Edit match scores" in edit_page.text
    assert f'hx-post="/match/{match_id}/edit"' in edit_page.text
    assert 'name="score_team_1"' in edit_page.text
    assert 'value="5"' in edit_page.text
    assert 'value="2"' in edit_page.text

    response = client.post(
        f"/match/{match_id}/edit",
        json={
            "date": "2024-01-02T12:00:00",
            "player_1": str(uuid.UUID(int=1)),
            "player_2": str(uuid.UUID(int=2)),
            "score_team_1": 2,
            "player_3": str(uuid.UUID(int=3)),
            "player_4": str(uuid.UUID(int=4)),
            "score_team_2": 8,
        },
    )

    assert response.status_code == 200
    assert f"/match/{match_id}" in response.headers["HX-Push-Url"]
    assert "Match scores updated" in response.text
    assert "Team 1 Score: 8" in response.text
    assert "Team 2 Score: 2" in response.text
    with Session(engine) as session:
        match = session.get(tables.Match, match_id)
        assert match.id == match_id
        assert (match.winning_team_id, match.losing_team_id, match.winning_team_score, match.losing_team_score) == (
            team_ids[1],
            team_ids[0],
            8,
            2,
        )
        assert set(
            session.execute(select(tables.TeamMatch.team_id).where(tables.TeamMatch.match_id == match_id)).scalars()
        ) == set(team_ids)


def test_unconfigured_admin_hides_mutations_and_preserves_public_browsing_and_submission(configured_site):
    _, engine, tables, match_id, _, make_app, settings_type = configured_site
    app = make_app(settings_type(admin_username=None, admin_password=None, admin_session_secret=None))

    with TestClient(app) as client:
        for path in ("/", "/match", "/player", f"/match/{match_id}"):
            assert client.get(path).status_code == 200

        match_detail = client.get(f"/match/{match_id}")
        assert "Edit match" not in match_detail.text
        assert "Remove match" not in match_detail.text
        assert "Administrator sign in" not in match_detail.text
        assert client.get("/admin/login").status_code == 404
        assert client.get(f"/match/{match_id}/remove").status_code == 404
        assert client.post(f"/match/{match_id}/edit", json={"score_team_1": 8, "score_team_2": 3}).status_code == 404
        assert client.post(f"/match/{match_id}/remove", json={}).status_code == 404

        submitted = client.post(
            "/match/submit",
            json={
                "player_1": str(uuid.UUID(int=1)),
                "player_3": str(uuid.UUID(int=3)),
                "score_team_1": 4,
                "score_team_2": 1,
                "date": "2024-01-03T12:00:00",
            },
        )
        assert submitted.status_code == 200
        assert submitted.headers["HX-Push-Url"].startswith("/match/")

    with Session(engine) as session:
        assert session.query(tables.Match).count() == 2
        new_match = session.execute(select(tables.Match).where(tables.Match.id != match_id)).scalar_one()
        assert (new_match.winning_team_score, new_match.losing_team_score) == (4, 1)


def test_played_at_correction_replays_equal_times_in_match_id_order(configured_site):
    client, engine, tables, first_match_id, team_ids, *_ = configured_site
    second_match_id = uuid.UUID(int=200)
    second_team_match_ids = (uuid.UUID(int=303), uuid.UUID(int=304))
    match_time = datetime(2024, 1, 3, 12)
    with Session(engine) as session:
        session.add(
            tables.Match(
                id=second_match_id,
                created_at=match_time,
                winning_team_id=team_ids[1],
                losing_team_id=team_ids[0],
                winning_team_score=3,
                losing_team_score=1,
            )
        )
        session.flush()
        session.add_all(
            [
                tables.TeamMatch(
                    id=second_team_match_ids[0],
                    team_id=team_ids[0],
                    match_id=second_match_id,
                    created_at=match_time,
                ),
                tables.TeamMatch(
                    id=second_team_match_ids[1],
                    team_id=team_ids[1],
                    match_id=second_match_id,
                    created_at=match_time,
                ),
            ]
        )
        session.add_all(
            [
                tables.PlayerRating(
                    id=uuid.UUID(int=601 + index),
                    match_id=second_match_id,
                    player_id=uuid.UUID(int=index + 1),
                    rating=1600 + index,
                    created_at=match_time,
                )
                for index in range(4)
            ]
            + [
                tables.TeamRating(
                    id=uuid.UUID(int=701 + index),
                    team_match_id=second_team_match_ids[index],
                    rating=1600 + index,
                    created_at=match_time,
                )
                for index in range(2)
            ]
        )
        session.commit()

    with Session(engine) as session:
        prior_player_ratings = dict(
            session.execute(
                select(tables.PlayerRating.player_id, tables.PlayerRating.rating).where(
                    tables.PlayerRating.match_id == second_match_id
                )
            ).all()
        )
        prior_team_ratings = dict(
            session.execute(
                select(tables.TeamMatch.team_id, tables.TeamRating.rating)
                .join(tables.TeamRating, tables.TeamRating.team_match_id == tables.TeamMatch.id)
                .where(tables.TeamMatch.match_id == second_match_id)
            ).all()
        )

    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    response = client.post(
        f"/match/{first_match_id}/edit",
        json={"score_team_1": 2, "score_team_2": 8, "date": match_time.isoformat()},
    )
    assert response.status_code == 200

    with Session(engine) as session:
        replayed_player_ratings = dict(
            session.execute(
                select(tables.PlayerRating.player_id, tables.PlayerRating.rating).where(
                    tables.PlayerRating.match_id == second_match_id
                )
            ).all()
        )
        replayed_team_ratings = dict(
            session.execute(
                select(tables.TeamMatch.team_id, tables.TeamRating.rating)
                .join(tables.TeamRating, tables.TeamRating.team_match_id == tables.TeamMatch.id)
                .where(tables.TeamMatch.match_id == second_match_id)
            ).all()
        )
        assert replayed_player_ratings != prior_player_ratings
        assert replayed_team_ratings != prior_team_ratings
        first_match_player_rating = session.execute(
            select(tables.PlayerRating.rating)
            .where(tables.PlayerRating.match_id == first_match_id)
            .where(tables.PlayerRating.player_id == uuid.UUID(int=1))
        ).scalar_one()
        second_match_player_rating = session.execute(
            select(tables.PlayerRating.rating)
            .where(tables.PlayerRating.match_id == second_match_id)
            .where(tables.PlayerRating.player_id == uuid.UUID(int=1))
        ).scalar_one()
        assert second_match_player_rating > first_match_player_rating
        team_1_ratings = dict(
            session.execute(
                select(tables.TeamMatch.match_id, tables.TeamRating.rating)
                .join(tables.TeamRating, tables.TeamRating.team_match_id == tables.TeamMatch.id)
                .where(tables.TeamMatch.team_id == team_ids[0])
                .where(tables.TeamMatch.match_id.in_((first_match_id, second_match_id)))
            ).all()
        )
        assert team_1_ratings[second_match_id] > team_1_ratings[first_match_id]
        assert session.get(tables.Match, first_match_id).created_at == match_time


def test_score_correction_uses_submission_score_limits_and_rejects_draws(configured_site):
    client, engine, tables, match_id, *_ = configured_site
    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})

    for scores in ({"score_team_1": 11, "score_team_2": 2}, {"score_team_1": 4, "score_team_2": 4}):
        response = client.post(f"/match/{match_id}/edit", json=scores)
        assert response.status_code == 400

    rejected_submission = client.post(
        "/match/submit",
        json={
            "player_1": str(uuid.UUID(int=1)),
            "player_3": str(uuid.UUID(int=3)),
            "score_team_1": 4,
            "score_team_2": 4,
            "date": "2024-01-03T12:00:00",
        },
    )
    assert rejected_submission.status_code == 400

    with Session(engine) as session:
        match = session.get(tables.Match, match_id)
        assert (match.winning_team_score, match.losing_team_score) == (5, 2)
        assert session.query(tables.PlayerRating).count() == 4
        assert session.query(tables.TeamRating).count() == 2


def test_score_correction_rolls_back_match_and_ratings_when_replay_write_fails(configured_site):
    client, engine, tables, match_id, *_ = configured_site
    replacement_player = uuid.UUID(int=5)
    with Session(engine) as session:
        session.add(tables.Player(id=replacement_player, name="Player 5", created_at=datetime(2024, 1, 1)))
        session.commit()
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER fail_team_rating_write BEFORE INSERT ON team_rating "
            "BEGIN SELECT RAISE(ABORT, 'simulated rating persistence failure'); END"
        )

    with Session(engine) as session:
        match_before = session.get(tables.Match, match_id)
        original_match = (
            match_before.id,
            match_before.created_at,
            match_before.winning_team_id,
            match_before.losing_team_id,
            match_before.winning_team_score,
            match_before.losing_team_score,
        )
        original_player_ratings = session.execute(
            select(
                tables.PlayerRating.id,
                tables.PlayerRating.match_id,
                tables.PlayerRating.player_id,
                tables.PlayerRating.rating,
            ).order_by(tables.PlayerRating.id)
        ).all()
        original_team_ratings = session.execute(
            select(tables.TeamRating.id, tables.TeamRating.team_match_id, tables.TeamRating.rating).order_by(
                tables.TeamRating.id
            )
        ).all()
        original_team_matches = session.execute(
            select(
                tables.TeamMatch.id,
                tables.TeamMatch.team_id,
                tables.TeamMatch.match_id,
                tables.TeamMatch.created_at,
            )
            .where(tables.TeamMatch.match_id == match_id)
            .order_by(tables.TeamMatch.id)
        ).all()

    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    response = client.post(
        f"/match/{match_id}/edit",
        json={
            "player_1": str(replacement_player),
            "player_2": None,
            "player_3": str(uuid.UUID(int=3)),
            "player_4": str(uuid.UUID(int=4)),
            "score_team_1": 2,
            "score_team_2": 8,
            "date": "2024-01-01T12:00:00",
        },
    )

    assert response.status_code == 500
    with Session(engine) as session:
        match_after = session.get(tables.Match, match_id)
        assert (
            match_after.id,
            match_after.created_at,
            match_after.winning_team_id,
            match_after.losing_team_id,
            match_after.winning_team_score,
            match_after.losing_team_score,
        ) == original_match
        assert (
            session.execute(
                select(
                    tables.PlayerRating.id,
                    tables.PlayerRating.match_id,
                    tables.PlayerRating.player_id,
                    tables.PlayerRating.rating,
                ).order_by(tables.PlayerRating.id)
            ).all()
            == original_player_ratings
        )
        assert (
            session.execute(
                select(tables.TeamRating.id, tables.TeamRating.team_match_id, tables.TeamRating.rating).order_by(
                    tables.TeamRating.id
                )
            ).all()
            == original_team_ratings
        )
        assert (
            session.execute(
                select(
                    tables.TeamMatch.id,
                    tables.TeamMatch.team_id,
                    tables.TeamMatch.match_id,
                    tables.TeamMatch.created_at,
                )
                .where(tables.TeamMatch.match_id == match_id)
                .order_by(tables.TeamMatch.id)
            ).all()
            == original_team_matches
        )
        assert (
            session.execute(select(tables.Team.id).where(tables.Team.team_player_1_id == replacement_player))
            .scalars()
            .all()
            == []
        )


def test_anonymous_score_correction_is_rejected_without_changing_match_or_ratings(configured_site):
    client, engine, tables, match_id, _, *_ = configured_site

    edit_page = client.get(f"/match/{match_id}/edit")
    assert edit_page.status_code == 401

    response = client.post(
        f"/match/{match_id}/edit",
        json={
            "player_1": str(uuid.UUID(int=5)),
            "player_2": None,
            "player_3": str(uuid.UUID(int=3)),
            "player_4": str(uuid.UUID(int=4)),
            "score_team_1": 8,
            "score_team_2": 3,
        },
    )

    assert response.status_code == 401
    with Session(engine) as session:
        match = session.get(tables.Match, match_id)
        assert (match.winning_team_id, match.losing_team_id, match.winning_team_score, match.losing_team_score) == (
            uuid.UUID(int=101),
            uuid.UUID(int=102),
            5,
            2,
        )
        assert session.execute(
            select(tables.PlayerRating.rating).order_by(tables.PlayerRating.player_id)
        ).scalars().all() == [1500, 1501, 1502, 1503]
        assert session.execute(
            select(tables.TeamRating.rating).order_by(tables.TeamRating.team_match_id)
        ).scalars().all() == [1500, 1501]


@pytest.mark.parametrize(
    ("team_1_player_2", "team_2_player_2", "expected_team_1", "expected_team_2"),
    [
        (None, uuid.UUID(int=6), {uuid.UUID(int=5)}, {uuid.UUID(int=1), uuid.UUID(int=6)}),
        (uuid.UUID(int=6), None, {uuid.UUID(int=5), uuid.UUID(int=6)}, {uuid.UUID(int=1)}),
    ],
)
def test_administrator_corrects_match_lineup_for_one_and_two_player_teams(
    configured_site, team_1_player_2, team_2_player_2, expected_team_1, expected_team_2
):
    client, engine, tables, match_id, _, *_ = configured_site
    replacement_player = uuid.UUID(int=5)
    additional_teammate = uuid.UUID(int=6)
    played_at = datetime(2024, 1, 2, 12)
    with Session(engine) as session:
        session.add_all(
            [
                tables.Player(id=replacement_player, name="Player 5", created_at=datetime(2024, 1, 1)),
                tables.Player(id=additional_teammate, name="Player 6", created_at=datetime(2024, 1, 1)),
            ]
        )
        session.commit()

    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    edit_page = client.get(f"/match/{match_id}/edit")
    assert edit_page.status_code == 200
    assert 'name="player_1"' in edit_page.text
    assert 'name="player_2"' in edit_page.text
    assert 'name="player_3"' in edit_page.text
    assert 'name="player_4"' in edit_page.text

    response = client.post(
        f"/match/{match_id}/edit",
        json={
            "player_1": str(replacement_player),
            "player_2": str(team_1_player_2) if team_1_player_2 else None,
            "player_3": str(uuid.UUID(int=1)),
            "player_4": str(team_2_player_2) if team_2_player_2 else None,
            "score_team_1": 5,
            "score_team_2": 2,
        },
    )
    assert response.status_code == 200
    assert "Match lineup updated" in response.text

    with Session(engine) as session:
        match = session.get(tables.Match, match_id)
        assert match.id == match_id
        assert match.created_at == played_at
        assert (match.winning_team_score, match.losing_team_score) == (5, 2)
        team_memberships = session.execute(
            select(tables.TeamMatch.team_id, tables.Team.team_player_1_id, tables.Team.team_player_2_id)
            .join(tables.Team, tables.TeamMatch.team_id == tables.Team.id)
            .where(tables.TeamMatch.match_id == match_id)
        ).all()
        assert {
            frozenset(player_id for player_id in (player_1, player_2) if player_id is not None)
            for _, player_1, player_2 in team_memberships
        } == {frozenset(expected_team_1), frozenset(expected_team_2)}
        assert (
            set(
                session.execute(
                    select(tables.PlayerRating.player_id).where(tables.PlayerRating.match_id == match_id)
                ).scalars()
            )
            == expected_team_1 | expected_team_2
        )
        team_rating_count = (
            session.execute(
                select(tables.TeamRating.id)
                .join(tables.TeamMatch, tables.TeamRating.team_match_id == tables.TeamMatch.id)
                .where(tables.TeamMatch.match_id == match_id)
            )
            .scalars()
            .all()
        )
        assert len(team_rating_count) == 2


def test_inactive_match_participant_remains_visible_and_can_be_kept(configured_site):
    client, engine, tables, match_id, _, *_ = configured_site
    inactive_player = uuid.UUID(int=2)
    with Session(engine) as session:
        player = session.get(tables.Player, inactive_player)
        player.active = False
        session.commit()

    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    edit_page = client.get(f"/match/{match_id}/edit")
    assert edit_page.status_code == 200
    assert "Player 2" in edit_page.text
    assert f'value="{inactive_player}" selected="selected"' in edit_page.text

    response = client.post(
        f"/match/{match_id}/edit",
        json={
            "player_1": str(uuid.UUID(int=1)),
            "player_2": str(inactive_player),
            "player_3": str(uuid.UUID(int=3)),
            "player_4": str(uuid.UUID(int=4)),
            "score_team_1": 5,
            "score_team_2": 2,
        },
    )
    assert response.status_code == 200

    with Session(engine) as session:
        assert set(
            session.execute(
                select(tables.PlayerRating.player_id).where(tables.PlayerRating.match_id == match_id)
            ).scalars()
        ) == {uuid.UUID(int=index) for index in range(1, 5)}


def test_invalid_player_references_leave_match_membership_and_rating_history_unchanged(configured_site):
    client, engine, tables, match_id, _, *_ = configured_site
    inactive_player = uuid.UUID(int=5)
    with Session(engine) as session:
        session.add(
            tables.Player(
                id=inactive_player,
                name="Inactive player",
                active=False,
                created_at=datetime(2024, 1, 1),
            )
        )
        session.commit()

    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    for selected_player in (uuid.UUID(int=6), inactive_player):
        response = client.post(
            f"/match/{match_id}/edit",
            json={
                "player_1": str(selected_player),
                "player_2": None,
                "player_3": str(uuid.UUID(int=3)),
                "player_4": str(uuid.UUID(int=4)),
                "score_team_1": 5,
                "score_team_2": 2,
            },
        )
        assert response.status_code == 400

        with Session(engine) as session:
            match = session.get(tables.Match, match_id)
            assert (
                match.id,
                match.created_at,
                match.winning_team_id,
                match.losing_team_id,
                match.winning_team_score,
                match.losing_team_score,
            ) == (
                match_id,
                datetime(2024, 1, 2, 12),
                uuid.UUID(int=101),
                uuid.UUID(int=102),
                5,
                2,
            )
            assert session.execute(
                select(tables.TeamMatch.id, tables.TeamMatch.team_id)
                .where(tables.TeamMatch.match_id == match_id)
                .order_by(tables.TeamMatch.id)
            ).all() == [(uuid.UUID(int=301), uuid.UUID(int=101)), (uuid.UUID(int=302), uuid.UUID(int=102))]
            assert session.execute(
                select(tables.PlayerRating.player_id, tables.PlayerRating.rating)
                .where(tables.PlayerRating.match_id == match_id)
                .order_by(tables.PlayerRating.player_id)
            ).all() == [(uuid.UUID(int=index), 1499 + index) for index in range(1, 5)]
            assert session.execute(
                select(tables.TeamRating.team_match_id, tables.TeamRating.rating).order_by(
                    tables.TeamRating.team_match_id
                )
            ).all() == [(uuid.UUID(int=301), 1500), (uuid.UUID(int=302), 1501)]


def test_lineup_correction_replays_downstream_player_and_team_ratings(configured_site):
    client, engine, tables, match_id, team_ids, *_ = configured_site
    replacement_player = uuid.UUID(int=5)
    later_match_id = uuid.UUID(int=202)
    later_team_match_ids = (uuid.UUID(int=303), uuid.UUID(int=304))
    later_time = datetime(2024, 1, 3, 12)
    with Session(engine) as session:
        session.add(tables.Player(id=replacement_player, name="Player 5", created_at=datetime(2024, 1, 1)))
        session.flush()
        session.add(
            tables.Match(
                id=later_match_id,
                created_at=later_time,
                winning_team_id=team_ids[1],
                losing_team_id=team_ids[0],
                winning_team_score=3,
                losing_team_score=1,
            )
        )
        session.flush()
        session.add_all(
            [
                tables.TeamMatch(
                    id=later_team_match_ids[0],
                    team_id=team_ids[0],
                    match_id=later_match_id,
                    created_at=later_time,
                ),
                tables.TeamMatch(
                    id=later_team_match_ids[1],
                    team_id=team_ids[1],
                    match_id=later_match_id,
                    created_at=later_time,
                ),
            ]
        )
        session.add_all(
            [
                tables.PlayerRating(
                    id=uuid.UUID(int=601 + index),
                    match_id=later_match_id,
                    player_id=uuid.UUID(int=index + 1),
                    rating=1600 + index,
                    created_at=later_time,
                )
                for index in range(4)
            ]
            + [
                tables.TeamRating(
                    id=uuid.UUID(int=701 + index),
                    team_match_id=later_team_match_ids[index],
                    rating=1600 + index,
                    created_at=later_time,
                )
                for index in range(2)
            ]
        )
        session.commit()

    with Session(engine) as session:
        previous_player_ratings = dict(
            session.execute(
                select(tables.PlayerRating.player_id, tables.PlayerRating.rating).where(
                    tables.PlayerRating.match_id == later_match_id
                )
            ).all()
        )
        previous_team_ratings = dict(
            session.execute(
                select(tables.TeamMatch.team_id, tables.TeamRating.rating)
                .join(tables.TeamRating, tables.TeamRating.team_match_id == tables.TeamMatch.id)
                .where(tables.TeamMatch.match_id == later_match_id)
            ).all()
        )

    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    response = client.post(
        f"/match/{match_id}/edit",
        json={
            "player_1": str(uuid.UUID(int=1)),
            "player_2": str(replacement_player),
            "player_3": str(uuid.UUID(int=3)),
            "player_4": str(uuid.UUID(int=4)),
            "score_team_1": 5,
            "score_team_2": 2,
        },
    )
    assert response.status_code == 200

    with Session(engine) as session:
        replayed_player_ratings = dict(
            session.execute(
                select(tables.PlayerRating.player_id, tables.PlayerRating.rating).where(
                    tables.PlayerRating.match_id == later_match_id
                )
            ).all()
        )
        replayed_team_ratings = dict(
            session.execute(
                select(tables.TeamMatch.team_id, tables.TeamRating.rating)
                .join(tables.TeamRating, tables.TeamRating.team_match_id == tables.TeamMatch.id)
                .where(tables.TeamMatch.match_id == later_match_id)
            ).all()
        )
        assert replayed_player_ratings != previous_player_ratings
        assert replayed_team_ratings != previous_team_ratings
        assert session.execute(
            select(tables.Match.created_at).where(tables.Match.id == match_id)
        ).scalar_one() == datetime(2024, 1, 2, 12)


@pytest.mark.parametrize(
    ("corrected_time", "subsequent_time"),
    [
        (datetime(2024, 1, 1, 12), datetime(2024, 1, 1, 18)),
        (datetime(2024, 1, 3, 12), datetime(2024, 1, 3, 12)),
        (datetime(2024, 1, 4, 12), datetime(2024, 1, 3, 12)),
    ],
)
def test_administrator_corrects_played_at_and_replays_history(configured_site, corrected_time, subsequent_time):
    client, engine, tables, match_id, team_ids, *_ = configured_site
    subsequent_match_id = uuid.UUID(int=202)
    with Session(engine) as session:
        session.add(
            tables.Match(
                id=subsequent_match_id,
                created_at=subsequent_time,
                winning_team_id=team_ids[1],
                losing_team_id=team_ids[0],
                winning_team_score=4,
                losing_team_score=1,
            )
        )
        session.flush()
        session.add_all(
            [
                tables.TeamMatch(
                    id=uuid.UUID(int=303 + index),
                    team_id=team_id,
                    match_id=subsequent_match_id,
                    created_at=subsequent_time,
                )
                for index, team_id in enumerate(team_ids)
            ]
            + [
                tables.PlayerRating(
                    id=uuid.UUID(int=801 + index),
                    match_id=subsequent_match_id,
                    player_id=uuid.UUID(int=index + 1),
                    rating=1600 + index,
                    created_at=subsequent_time,
                )
                for index in range(4)
            ]
            + [
                tables.TeamRating(
                    id=uuid.UUID(int=901 + index),
                    team_match_id=uuid.UUID(int=303 + index),
                    rating=1600 + index,
                    created_at=subsequent_time,
                )
                for index in range(2)
            ]
        )
        session.commit()

    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    edit_page = client.get(f"/match/{match_id}/edit")
    assert edit_page.status_code == 200
    assert 'name="date"' in edit_page.text
    assert "Played at (UTC)" in edit_page.text
    assert 'value="2024-01-02T12:00:00"' in edit_page.text
    assert 'step="1"' in edit_page.text
    assert "border border-base-content rounded-lg shadow-lg w-full items-center" in edit_page.text
    assert "flex flex-col items-center justify-center gap-4 pb-2 w-full" in edit_page.text
    assert "Team 1 score" in edit_page.text
    assert "Team 2 score" in edit_page.text

    response = client.post(
        f"/match/{match_id}/edit",
        json={
            "date": corrected_time.isoformat(timespec="minutes"),
            "score_team_1": 5,
            "score_team_2": 2,
        },
    )
    assert response.status_code == 200

    with Session(engine) as session:
        match = session.get(tables.Match, match_id)
        assert (match.id, match.created_at, match.winning_team_id, match.losing_team_id) == (
            match_id,
            corrected_time,
            team_ids[0],
            team_ids[1],
        )
        assert (match.winning_team_score, match.losing_team_score) == (5, 2)
        assert session.execute(
            select(tables.TeamMatch.created_at)
            .where(tables.TeamMatch.match_id == match_id)
            .order_by(tables.TeamMatch.id)
        ).scalars().all() == [corrected_time, corrected_time]
        assert session.execute(
            select(tables.PlayerRating.rating).where(tables.PlayerRating.match_id == subsequent_match_id)
        ).scalars().all() != [1600, 1601, 1602, 1603]
        assert session.execute(
            select(tables.TeamRating.rating)
            .join(tables.TeamMatch, tables.TeamRating.team_match_id == tables.TeamMatch.id)
            .where(tables.TeamMatch.match_id == subsequent_match_id)
        ).scalars().all() != [1600, 1601]


def test_administrator_can_review_and_cancel_match_removal_without_changes(configured_site):
    client, engine, tables, match_id, *_ = configured_site

    public_detail = client.get(f"/match/{match_id}")
    assert public_detail.status_code == 200
    assert "Remove match" not in public_detail.text

    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    admin_detail = client.get(f"/match/{match_id}")
    assert f'href="/match/{match_id}/remove"' in admin_detail.text

    confirmation = client.get(f"/match/{match_id}/remove")
    assert confirmation.status_code == 200
    assert "Permanently remove this match?" in confirmation.text
    assert "Player 1 &amp; Player 2" in confirmation.text
    assert "Player 3 &amp; Player 4" in confirmation.text
    assert "5" in confirmation.text and "2" in confirmation.text
    assert f'hx-post="/match/{match_id}/remove"' in confirmation.text
    assert f'href="/match/{match_id}"' in confirmation.text
    assert "Cancel" in confirmation.text
    cancelled = client.get(f"/match/{match_id}")
    assert cancelled.status_code == 200
    assert "Match Details" in cancelled.text

    with Session(engine) as session:
        assert session.get(tables.Match, match_id) is not None
        assert session.query(tables.PlayerRating).count() == 4
        assert session.query(tables.TeamMatch).count() == 2
        assert session.query(tables.TeamRating).count() == 2


def test_anonymous_match_removal_is_rejected_without_changes(configured_site):
    client, engine, tables, match_id, *_ = configured_site

    assert client.get(f"/match/{match_id}/remove").status_code == 401
    response = client.post(f"/match/{match_id}/remove", json={})
    assert response.status_code == 401

    with Session(engine) as session:
        assert session.get(tables.Match, match_id) is not None
        assert session.query(tables.PlayerRating).count() == 4
        assert session.query(tables.TeamMatch).count() == 2
        assert session.query(tables.TeamRating).count() == 2


def _seed_following_match(engine, tables, team_ids):
    following_match_id = uuid.UUID(int=202)
    following_team_match_ids = (uuid.UUID(int=303), uuid.UUID(int=304))
    following_time = datetime(2024, 1, 3, 12)
    with Session(engine) as session:
        session.add(
            tables.Match(
                id=following_match_id,
                created_at=following_time,
                winning_team_id=team_ids[1],
                losing_team_id=team_ids[0],
                winning_team_score=4,
                losing_team_score=1,
            )
        )
        session.flush()
        session.add_all(
            [
                tables.TeamMatch(
                    id=following_team_match_ids[index],
                    team_id=team_id,
                    match_id=following_match_id,
                    created_at=following_time,
                )
                for index, team_id in enumerate(team_ids)
            ]
            + [
                tables.PlayerRating(
                    id=uuid.UUID(int=601 + index),
                    match_id=following_match_id,
                    player_id=uuid.UUID(int=index + 1),
                    rating=1600 + index,
                    created_at=following_time,
                )
                for index in range(4)
            ]
            + [
                tables.TeamRating(
                    id=uuid.UUID(int=701 + index),
                    team_match_id=following_team_match_ids[index],
                    rating=1600 + index,
                    created_at=following_time,
                )
                for index in range(2)
            ]
        )
        session.commit()
    return following_match_id


def test_administrator_removes_match_and_replays_remaining_ratings(configured_site):
    client, engine, tables, match_id, team_ids, *_ = configured_site
    following_match_id = _seed_following_match(engine, tables, team_ids)

    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    response = client.post(f"/match/{match_id}/remove", json={})

    assert response.status_code == 200
    assert response.headers["HX-Push-Url"] == "/match"
    assert "Team 1 score" in response.text
    assert "Match removed" in response.text

    with Session(engine) as session:
        assert session.get(tables.Match, match_id) is None
        assert session.get(tables.Match, following_match_id) is not None
        assert session.query(tables.Match).count() == 1
        assert session.query(tables.PlayerRating).count() == 4
        assert session.query(tables.TeamMatch).count() == 2
        assert session.query(tables.TeamRating).count() == 2
        assert (
            session.execute(select(tables.PlayerRating.id).where(tables.PlayerRating.match_id == match_id))
            .scalars()
            .all()
            == []
        )
        assert (
            session.execute(select(tables.TeamMatch.id).where(tables.TeamMatch.match_id == match_id)).scalars().all()
            == []
        )
        assert (
            session.execute(
                select(tables.TeamRating.id).where(
                    tables.TeamRating.team_match_id.in_((uuid.UUID(int=301), uuid.UUID(int=302)))
                )
            )
            .scalars()
            .all()
            == []
        )
        assert set(session.execute(select(tables.Player.id)).scalars()) == {
            uuid.UUID(int=index) for index in range(1, 5)
        }
        assert set(session.execute(select(tables.Team.id)).scalars()) == set(team_ids)
        following_player_ratings = dict(
            session.execute(
                select(tables.PlayerRating.player_id, tables.PlayerRating.rating).where(
                    tables.PlayerRating.match_id == following_match_id
                )
            ).all()
        )
        assert following_player_ratings == {
            uuid.UUID(int=1): 1445,
            uuid.UUID(int=2): 1445,
            uuid.UUID(int=3): 1555,
            uuid.UUID(int=4): 1555,
        }
        following_team_ratings = dict(
            session.execute(
                select(tables.TeamMatch.team_id, tables.TeamRating.rating)
                .join(tables.TeamRating, tables.TeamRating.team_match_id == tables.TeamMatch.id)
                .where(tables.TeamMatch.match_id == following_match_id)
            ).all()
        )
        assert len(following_team_ratings) == 2
        assert following_team_ratings[team_ids[0]] < 1500
        assert following_team_ratings[team_ids[1]] > 1500


def test_match_removal_rolls_back_if_rating_replay_fails(configured_site):
    client, engine, tables, match_id, team_ids, *_ = configured_site
    _seed_following_match(engine, tables, team_ids)
    with Session(engine) as session:
        original_matches = session.execute(
            select(
                tables.Match.id,
                tables.Match.created_at,
                tables.Match.winning_team_id,
                tables.Match.losing_team_id,
                tables.Match.winning_team_score,
                tables.Match.losing_team_score,
            ).order_by(tables.Match.id)
        ).all()
        original_player_ratings = session.execute(
            select(
                tables.PlayerRating.id,
                tables.PlayerRating.match_id,
                tables.PlayerRating.player_id,
                tables.PlayerRating.rating,
            ).order_by(tables.PlayerRating.id)
        ).all()
        original_team_matches = session.execute(
            select(
                tables.TeamMatch.id,
                tables.TeamMatch.team_id,
                tables.TeamMatch.match_id,
                tables.TeamMatch.created_at,
            ).order_by(tables.TeamMatch.id)
        ).all()
        original_team_ratings = session.execute(
            select(tables.TeamRating.id, tables.TeamRating.team_match_id, tables.TeamRating.rating).order_by(
                tables.TeamRating.id
            )
        ).all()

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER fail_team_rating_write BEFORE INSERT ON team_rating "
            "BEGIN SELECT RAISE(ABORT, 'simulated rating persistence failure'); END"
        )

    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    response = client.post(f"/match/{match_id}/remove", json={})

    assert response.status_code == 500
    with Session(engine) as session:
        assert (
            session.execute(
                select(
                    tables.Match.id,
                    tables.Match.created_at,
                    tables.Match.winning_team_id,
                    tables.Match.losing_team_id,
                    tables.Match.winning_team_score,
                    tables.Match.losing_team_score,
                ).order_by(tables.Match.id)
            ).all()
            == original_matches
        )
        assert (
            session.execute(
                select(
                    tables.PlayerRating.id,
                    tables.PlayerRating.match_id,
                    tables.PlayerRating.player_id,
                    tables.PlayerRating.rating,
                ).order_by(tables.PlayerRating.id)
            ).all()
            == original_player_ratings
        )
        assert (
            session.execute(
                select(
                    tables.TeamMatch.id,
                    tables.TeamMatch.team_id,
                    tables.TeamMatch.match_id,
                    tables.TeamMatch.created_at,
                ).order_by(tables.TeamMatch.id)
            ).all()
            == original_team_matches
        )
        assert (
            session.execute(
                select(tables.TeamRating.id, tables.TeamRating.team_match_id, tables.TeamRating.rating).order_by(
                    tables.TeamRating.id
                )
            ).all()
            == original_team_ratings
        )


def test_removing_missing_match_returns_not_found_without_changes(configured_site):
    client, engine, tables, match_id, *_ = configured_site
    missing_match_id = uuid.UUID(int=999)
    client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})

    assert client.get(f"/match/{missing_match_id}/remove").status_code == 404
    assert client.post(f"/match/{missing_match_id}/remove", json={}).status_code == 404

    with Session(engine) as session:
        assert session.get(tables.Match, match_id) is not None
        assert session.query(tables.Match).count() == 1
        assert session.query(tables.PlayerRating).count() == 4
        assert session.query(tables.TeamMatch).count() == 2
        assert session.query(tables.TeamRating).count() == 2

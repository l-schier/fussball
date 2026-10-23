from __future__ import annotations

import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session


def _sign_in_as_admin(client: TestClient) -> None:
    response = client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    assert response.status_code == 200


def test_administrator_can_review_and_cancel_match_removal_without_changes(configured_site):
    client, engine, tables, match_id, *_ = configured_site

    public_detail = client.get(f"/match/{match_id}")
    assert public_detail.status_code == 200
    assert "Remove match" not in public_detail.text

    _sign_in_as_admin(client)
    admin_detail = client.get(f"/match/{match_id}")
    assert f'href="/match/{match_id}/remove"' in admin_detail.text

    confirmation = client.get(f"/match/{match_id}/remove")
    assert confirmation.status_code == 200
    removal_post = confirmation.text.index(f'hx-post="/match/{match_id}/remove"')
    form_start = confirmation.text.rfind("<form", 0, removal_post)
    form_end = confirmation.text.index("</form>", removal_post)
    removal_form = confirmation.text[form_start:form_end]
    assert "Permanently remove this match?" in removal_form
    assert "Player 1 &amp; Player 2" in removal_form
    assert "Player 3 &amp; Player 4" in removal_form
    assert "5" in removal_form and "2" in removal_form
    assert f'href="/match/{match_id}"' in removal_form
    assert "Cancel" in removal_form
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

    _sign_in_as_admin(client)
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

    _sign_in_as_admin(client)
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
    _sign_in_as_admin(client)

    assert client.get(f"/match/{missing_match_id}/remove").status_code == 404
    assert client.post(f"/match/{missing_match_id}/remove", json={}).status_code == 404

    with Session(engine) as session:
        assert session.get(tables.Match, match_id) is not None
        assert session.query(tables.Match).count() == 1
        assert session.query(tables.PlayerRating).count() == 4
        assert session.query(tables.TeamMatch).count() == 2
        assert session.query(tables.TeamRating).count() == 2


def test_unconfigured_admin_cannot_remove_match(configured_site):
    _, engine, tables, match_id, _, make_app, settings_type = configured_site
    app = make_app(settings_type(admin_username=None, admin_password=None, admin_session_secret=None))

    with TestClient(app) as client:
        match_detail = client.get(f"/match/{match_id}")
        assert match_detail.status_code == 200
        assert "Remove match" not in match_detail.text
        assert client.get(f"/match/{match_id}/remove").status_code == 404
        assert client.post(f"/match/{match_id}/remove", json={}).status_code == 404

    with Session(engine) as session:
        assert session.get(tables.Match, match_id) is not None
        assert session.query(tables.PlayerRating).count() == 4
        assert session.query(tables.TeamMatch).count() == 2
        assert session.query(tables.TeamRating).count() == 2

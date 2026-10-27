from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session


def _record_match(engine, tables, match_number, team_1_players, team_2_players, winning_team_number):
    match_id = uuid.UUID(int=700 + match_number)
    team_ids = (uuid.UUID(int=800 + match_number * 2), uuid.UUID(int=801 + match_number * 2))
    played_at = datetime(2024, 1, match_number + 2, 12)
    players_by_team = (team_1_players, team_2_players)

    with Session(engine) as session:
        session.add_all(
            [
                tables.Team(
                    id=team_ids[index],
                    team_player_1_id=players[0],
                    team_player_2_id=players[1] if len(players) > 1 else None,
                    created_at=played_at,
                )
                for index, players in enumerate(players_by_team)
            ]
        )
        session.flush()
        session.add(
            tables.Match(
                id=match_id,
                created_at=played_at,
                winning_team_id=team_ids[winning_team_number],
                losing_team_id=team_ids[1 - winning_team_number],
                winning_team_score=5,
                losing_team_score=2,
            )
        )
        session.flush()
        session.add_all(
            [
                tables.TeamMatch(
                    id=uuid.UUID(int=900 + match_number * 2 + index),
                    team_id=team_id,
                    match_id=match_id,
                    created_at=played_at,
                )
                for index, team_id in enumerate(team_ids)
            ]
            + [
                tables.PlayerRating(
                    id=uuid.UUID(int=1000 + match_number * 10 + index),
                    match_id=match_id,
                    player_id=player_id,
                    rating=1500,
                    created_at=played_at,
                )
                for index, player_id in enumerate(team_1_players + team_2_players)
            ]
        )
        session.commit()


def test_player_profile_shows_lifetime_win_rate_for_inactive_player_and_both_team_sizes(configured_site):
    client, engine, tables, _, _, *_ = configured_site
    player_id = uuid.UUID(int=1)

    with Session(engine) as session:
        session.get(tables.Player, player_id).active = False
        session.commit()

    _record_match(
        engine,
        tables,
        match_number=1,
        team_1_players=(uuid.UUID(int=1), uuid.UUID(int=2)),
        team_2_players=(uuid.UUID(int=3), uuid.UUID(int=4)),
        winning_team_number=1,
    )
    _record_match(
        engine,
        tables,
        match_number=2,
        team_1_players=(uuid.UUID(int=1),),
        team_2_players=(uuid.UUID(int=3),),
        winning_team_number=0,
    )

    response = client.get(f"/player/{player_id}")

    assert response.status_code == 200
    assert "Total Matches: 3" in response.text
    assert "Lifetime Win Rate: 2 wins / 3 matches (66.7%)" in response.text


def test_player_profile_shows_no_matches_yet_without_a_percentage(configured_site):
    client, engine, tables, *_ = configured_site
    player_id = uuid.UUID(int=5)

    with Session(engine) as session:
        session.add(
            tables.Player(
                id=player_id,
                name="Player 5",
                active=True,
                created_at=datetime(2024, 1, 1),
            )
        )
        session.commit()

    response = client.get(f"/player/{player_id}")

    assert response.status_code == 200
    assert "Total Matches: 0" in response.text
    assert "No matches yet" in response.text
    assert "Lifetime Win Rate:" not in response.text
    assert "0.0%" not in response.text


def test_player_profile_reflects_match_corrections_and_removals(configured_site):
    client, _, _, match_id, *_ = configured_site
    player_id = uuid.UUID(int=1)

    before_correction = client.get(f"/player/{player_id}")
    assert "Lifetime Win Rate: 1 win / 1 match (100.0%)" in before_correction.text

    sign_in = client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    assert sign_in.status_code == 200
    correction = client.post(f"/match/{match_id}/edit", json={"score_team_1": 2, "score_team_2": 8})
    assert correction.status_code == 200

    after_correction = client.get(f"/player/{player_id}")
    assert "Lifetime Win Rate: 0 wins / 1 match (0.0%)" in after_correction.text

    removal = client.post(f"/match/{match_id}/remove", json={})
    assert removal.status_code == 200

    after_removal = client.get(f"/player/{player_id}")
    assert "Total Matches: 0" in after_removal.text
    assert "No matches yet" in after_removal.text
    assert "Lifetime Win Rate:" not in after_removal.text

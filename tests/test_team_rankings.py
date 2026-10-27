import uuid
from datetime import datetime
from html.parser import HTMLParser

from sqlalchemy.orm import Session


class TableRowsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def _add_following_ratings(engine, tables, team_ids: tuple[uuid.UUID, uuid.UUID]) -> None:
    match_id = uuid.UUID(int=202)
    played_at = datetime(2024, 2, 1, 12)
    team_match_ids = (uuid.UUID(int=303), uuid.UUID(int=304))

    with Session(engine) as session:
        old_ratings = session.query(tables.TeamRating).all()
        for rating in old_ratings:
            rating.rating = 2200 - (rating.team_match_id.int - 301) * 100

        session.add(
            tables.Match(
                id=match_id,
                created_at=played_at,
                winning_team_id=team_ids[1],
                losing_team_id=team_ids[0],
                winning_team_score=5,
                losing_team_score=2,
            )
        )
        session.flush()
        session.add_all(
            [
                tables.TeamMatch(
                    id=team_match_ids[index],
                    team_id=team_id,
                    match_id=match_id,
                    created_at=played_at,
                )
                for index, team_id in enumerate(team_ids)
            ]
            + [
                tables.TeamRating(
                    id=uuid.UUID(int=601 + index),
                    team_match_id=team_match_ids[index],
                    rating=rating,
                    created_at=played_at,
                )
                for index, rating in enumerate((1600, 1700))
            ]
        )
        session.commit()


def _add_team(engine, tables, team_number: int, players: list[tuple[int, str]]) -> uuid.UUID:
    team_id = uuid.UUID(int=team_number)
    player_ids = [uuid.UUID(int=player_number) for player_number, _ in players]
    with Session(engine) as session:
        session.add_all(
            [
                tables.Player(id=player_id, name=name, active=True, created_at=datetime(2024, 1, 1))
                for player_id, (_, name) in zip(player_ids, players)
            ]
        )
        session.add(
            tables.Team(
                id=team_id,
                team_player_1_id=player_ids[0],
                team_player_2_id=player_ids[1] if len(player_ids) > 1 else None,
                created_at=datetime(2024, 1, 1),
            )
        )
        session.commit()
    return team_id


def _record_match(
    engine, tables, match_number: int, team_ids: tuple[uuid.UUID, uuid.UUID], ratings: tuple[int | None, int | None]
) -> None:
    match_id = uuid.UUID(int=match_number)
    played_at = datetime(2024, 2, match_number - 201, 12)
    team_match_ids = (uuid.UUID(int=3000 + match_number * 2), uuid.UUID(int=3001 + match_number * 2))

    with Session(engine) as session:
        session.add(
            tables.Match(
                id=match_id,
                created_at=played_at,
                winning_team_id=team_ids[0],
                losing_team_id=team_ids[1],
                winning_team_score=5,
                losing_team_score=2,
            )
        )
        session.flush()
        session.add_all(
            [
                tables.TeamMatch(
                    id=team_match_ids[index],
                    team_id=team_id,
                    match_id=match_id,
                    created_at=played_at,
                )
                for index, team_id in enumerate(team_ids)
            ]
            + [
                tables.TeamRating(
                    id=uuid.UUID(int=4000 + match_number * 2 + index),
                    team_match_id=team_match_ids[index],
                    rating=rating,
                    created_at=played_at,
                )
                for index, rating in enumerate(ratings)
                if rating is not None
            ]
        )
        session.commit()


def test_team_rankings_show_latest_ratings_in_descending_order(configured_site) -> None:
    client, engine, tables, _, team_ids, *_ = configured_site
    _add_following_ratings(engine, tables, team_ids)

    response = client.get("/team")

    assert response.status_code == 200
    assert "Team Rankings" in response.text

    parser = TableRowsParser()
    parser.feed(response.text)
    team_rows = [row for row in parser.rows if "Player 3" in " ".join(row) or "Player 1" in " ".join(row)]

    assert len(team_rows) == 2
    assert "Player 3" in " ".join(team_rows[0])
    assert "Player 4" in " ".join(team_rows[0])
    assert "1700" in team_rows[0]
    assert "Player 1" in " ".join(team_rows[1])
    assert "Player 2" in " ".join(team_rows[1])
    assert "1600" in team_rows[1]
    assert "2200" not in response.text
    assert "2100" not in response.text


def test_team_rankings_share_tie_ranks_and_include_unranked_and_single_member_teams(configured_site) -> None:
    client, engine, tables, _, existing_team_ids, *_ = configured_site
    with Session(engine) as session:
        for rating in session.query(tables.TeamRating).all():
            rating.rating = 1600
        session.commit()

    one_member_team = _add_team(engine, tables, 103, [(5, "Zara")])
    alphabetically_first_team = _add_team(engine, tables, 104, [(6, "Abbey"), (7, "Ben")])
    lower_rated_team = _add_team(engine, tables, 105, [(8, "Maya"), (9, "Noah")])
    unrated_team = _add_team(engine, tables, 106, [(10, "Unrated")])
    _record_match(engine, tables, 202, (one_member_team, existing_team_ids[0]), (1600, 1600))
    _record_match(engine, tables, 203, (alphabetically_first_team, existing_team_ids[1]), (1600, 1600))
    _record_match(engine, tables, 204, (lower_rated_team, existing_team_ids[0]), (1400, 1600))
    _record_match(engine, tables, 205, (unrated_team, existing_team_ids[0]), (1500, 1600))
    _record_match(engine, tables, 206, (unrated_team, existing_team_ids[1]), (None, 1600))

    response = client.get("/team")

    assert response.status_code == 200
    parser = TableRowsParser()
    parser.feed(response.text)
    rows = [row for row in parser.rows if len(row) == 3 and row[0] != "Rank"]

    assert [row[0] for row in rows] == ["1", "1", "1", "1", "5", "Unranked"]
    assert [row[1] for row in rows] == [
        "Abbey & Ben",
        "Player 1 & Player 2",
        "Player 3 & Player 4",
        "Zara",
        "Maya & Noah",
        "Unrated",
    ]
    assert rows[3][2] == "1600"
    assert rows[4][2] == "1400"
    assert rows[5][2] == "—"


def test_team_rankings_reflect_ratings_after_a_match_is_removed(configured_site) -> None:
    client, engine, tables, _, team_ids, *_ = configured_site
    _add_following_ratings(engine, tables, team_ids)

    before_removal = client.get("/team")
    assert before_removal.status_code == 200
    assert "1700" in before_removal.text
    assert "1600" in before_removal.text

    sign_in = client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    assert sign_in.status_code == 200
    removed = client.post(f"/match/{uuid.UUID(int=202)}/remove", json={})
    assert removed.status_code == 200

    response = client.get("/team")

    assert response.status_code == 200
    parser = TableRowsParser()
    parser.feed(response.text)
    rows = [row for row in parser.rows if len(row) == 3 and row[0] != "Rank"]

    assert [row[0] for row in rows] == ["1", "2"]
    assert all(row[2] not in {"1600", "1700", "2100", "2200"} for row in rows)


def test_team_rankings_reflect_recalculated_ratings_after_a_match_is_corrected(configured_site) -> None:
    client, _, _, match_id, *_ = configured_site

    before_correction = client.get("/team")
    assert before_correction.status_code == 200
    before_parser = TableRowsParser()
    before_parser.feed(before_correction.text)
    before_rows = [row for row in before_parser.rows if len(row) == 3 and row[0] != "Rank"]
    before_ratings = {row[1]: row[2] for row in before_rows}
    assert [(row[0], row[1]) for row in before_rows] == [
        ("1", "Player 3 & Player 4"),
        ("2", "Player 1 & Player 2"),
    ]

    sign_in = client.post("/admin/sign-in", json={"username": "admin", "password": "correct horse battery staple"})
    assert sign_in.status_code == 200
    correction = client.post(
        f"/match/{match_id}/edit",
        json={"score_team_1": 8, "score_team_2": 2},
    )
    assert correction.status_code == 200

    response = client.get("/team")
    assert response.status_code == 200
    parser = TableRowsParser()
    parser.feed(response.text)
    rows = [row for row in parser.rows if len(row) == 3 and row[0] != "Rank"]

    assert [(row[0], row[1]) for row in rows] == [
        ("1", "Player 1 & Player 2"),
        ("2", "Player 3 & Player 4"),
    ]
    assert all(row[2] != before_ratings[row[1]] for row in rows)
    assert float(rows[0][2]) > float(rows[1][2])


def test_team_rankings_show_an_empty_state_when_no_teams_are_recorded(configured_site) -> None:
    client, engine, tables, *_ = configured_site
    with Session(engine) as session:
        session.query(tables.TeamRating).delete(synchronize_session=False)
        session.query(tables.TeamMatch).delete(synchronize_session=False)
        session.query(tables.Match).delete(synchronize_session=False)
        session.query(tables.Team).delete(synchronize_session=False)
        session.commit()

    response = client.get("/team")

    assert response.status_code == 200
    assert "Team Rankings" in response.text
    assert "No teams have been recorded yet." in response.text
    assert "<table" not in response.text

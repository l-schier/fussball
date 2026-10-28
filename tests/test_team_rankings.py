import uuid
from datetime import datetime
from html.parser import HTMLParser

from sqlalchemy.orm import Session


class TableRowsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.row_attributes: list[dict[str, str | None]] = []
        self._row: list[str] | None = None
        self._row_attributes: dict[str, str | None] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
            self._row_attributes = dict(attrs)
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
            self.row_attributes.append(self._row_attributes or {})
            self._row = None
            self._row_attributes = None


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


def test_team_rankings_round_ratings_without_changing_rank_order(configured_site) -> None:
    client, engine, tables, *_ = configured_site
    with Session(engine) as session:
        team_matches = session.query(tables.TeamMatch).order_by(tables.TeamMatch.team_id).all()
        for team_match, rating in zip(team_matches, (1645.6, 1645.8)):
            session.query(tables.TeamRating).filter_by(team_match_id=team_match.id).one().rating = rating
        session.commit()

    response = client.get("/team")

    assert response.status_code == 200
    parser = TableRowsParser()
    parser.feed(response.text)
    rows = [row for row in parser.rows if len(row) == 3 and row[0] != "Rank"]

    assert [(row[0], row[1], row[2]) for row in rows] == [
        ("1", "Player 3 & Player 4", "1646"),
        ("2", "Player 1 & Player 2", "1646"),
    ]


def test_team_rankings_hide_single_member_teams_and_keep_ties_and_unranked_teams(configured_site) -> None:
    client, engine, tables, _, existing_team_ids, *_ = configured_site
    with Session(engine) as session:
        for rating in session.query(tables.TeamRating).all():
            rating.rating = 1600
        session.commit()

    one_member_team = _add_team(engine, tables, 103, [(5, "Zara")])
    alphabetically_first_team = _add_team(engine, tables, 104, [(6, "Abbey"), (7, "Ben")])
    lower_rated_team = _add_team(engine, tables, 105, [(8, "Maya"), (9, "Noah")])
    unrated_team = _add_team(engine, tables, 106, [(10, "Unrated"), (11, "Teammate")])
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

    assert [row[0] for row in rows] == ["1", "1", "1", "4", "Unranked"]
    assert [row[1] for row in rows] == [
        "Abbey & Ben",
        "Player 1 & Player 2",
        "Player 3 & Player 4",
        "Maya & Noah",
        "Teammate & Unrated",
    ]
    assert "Zara" not in response.text
    assert rows[3][2] == "1400"
    assert rows[4][2] == "—"


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


def test_ranked_team_links_to_recent_match_history(configured_site) -> None:
    client, engine, tables, _, team_ids, *_ = configured_site
    _add_following_ratings(engine, tables, team_ids)

    rankings = client.get("/team")

    assert rankings.status_code == 200
    assert f'href="/team/{team_ids[0]}"' in rankings.text
    rankings_parser = TableRowsParser()
    rankings_parser.feed(rankings.text)
    team_row_index = next(index for index, row in enumerate(rankings_parser.rows) if row[1] == "Player 1 & Player 2")
    assert rankings_parser.row_attributes[team_row_index].get("onclick") == (
        f"window.location.href='/team/{team_ids[0]}'"
    )

    history = client.get(f"/team/{team_ids[0]}")

    assert history.status_code == 200
    assert "Player 1" in history.text
    assert "Player 2" in history.text
    assert "Recent matches" in history.text
    assert f'href="/match/{uuid.UUID(int=202)}"' in history.text
    assert 'id="team-rating-history-chart"' in history.text

    parser = TableRowsParser()
    parser.feed(history.text)
    match_rows = [row for row in parser.rows if len(row) == 5 and row[0] != "Played at"]

    assert match_rows[0] == ["2024-02-01 12:00:00", "Player 3 & Player 4", "2–5", "Loss", "1600"]


def test_team_details_include_rating_history_graph(configured_site) -> None:
    client, engine, tables, _, team_ids, *_ = configured_site
    _add_following_ratings(engine, tables, team_ids)

    response = client.get(f"/team/{team_ids[0]}")

    assert response.status_code == 200
    assert 'id="team-rating-history-chart"' in response.text
    assert "Current rating: 1600" in response.text
    assert "Total Matches: 2" in response.text
    assert "Lifetime Win Rate: 1 win / 2 matches (50.0%)" in response.text


def test_team_match_history_paginates_like_player_ratings(configured_site) -> None:
    client, engine, tables, _, team_ids, *_ = configured_site
    for match_number in range(202, 212):
        _record_match(engine, tables, match_number, team_ids, (1600, 1700))

    page_one = client.get(f"/team/{team_ids[0]}")

    assert page_one.status_code == 200
    assert "Page 1 of 2" in page_one.text
    assert f'hx-post="/team/{team_ids[0]}/matches/2"' in page_one.text

    page_two = client.post(f"/team/{team_ids[0]}/matches/2")

    assert page_two.status_code == 200
    assert "Page 2 of 2" in page_two.text
    assert "2024-01-02 12:00:00" in page_two.text

    out_of_range_page = client.post(f"/team/{team_ids[0]}/matches/99")

    assert out_of_range_page.status_code == 200
    assert "Page 2 of 2" in out_of_range_page.text

    page_zero = client.post(f"/team/{team_ids[0]}/matches/0")

    assert page_zero.status_code == 200
    assert "Page 1 of 2" in page_zero.text


def test_team_details_return_not_found_for_invalid_or_unknown_ids(configured_site) -> None:
    client, *_ = configured_site

    invalid_id = client.get("/team/not-a-uuid")
    unknown_id = client.get(f"/team/{uuid.UUID(int=999)}")

    assert invalid_id.status_code == 404
    assert unknown_id.status_code == 404


def test_team_details_show_an_empty_state_for_a_team_without_matches(configured_site) -> None:
    client, engine, tables, *_ = configured_site
    team_id = _add_team(engine, tables, 107, [(12, "Unplayed A"), (13, "Unplayed B")])

    response = client.get(f"/team/{team_id}")

    assert response.status_code == 200
    assert "Unplayed A" in response.text
    assert "Unplayed B" in response.text
    assert "No matches have been recorded for this team yet." in response.text
    assert "Current rating: Unranked" in response.text
    assert "Total Matches: 0" in response.text
    assert "No matches yet" in response.text
    assert 'id="team-rating-history-chart"' in response.text
    assert "<table" not in response.text


def test_single_player_teams_keep_ratings_but_are_not_listed(configured_site) -> None:
    client, engine, tables, *_ = configured_site
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
    match_id = uuid.UUID(submitted.headers["HX-Push-Url"].rsplit("/", 1)[1])
    with Session(engine) as session:
        team_matches = session.query(tables.TeamMatch).filter_by(match_id=match_id).all()
        assert len(team_matches) == 2
        single_player_team_ids = [team_match.team_id for team_match in team_matches]
        assert all(session.get(tables.Team, team_id).team_player_2_id is None for team_id in single_player_team_ids)
        assert all(
            session.query(tables.TeamRating).filter_by(team_match_id=team_match.id).count() == 1
            for team_match in team_matches
        )

    rankings = client.get("/team")

    assert rankings.status_code == 200
    assert all(f'href="/team/{team_id}"' not in rankings.text for team_id in single_player_team_ids)

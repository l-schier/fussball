from collections.abc import Sequence
from typing import Any
from uuid import UUID

from database.tables import Match, Player, PlayerRating, Team, TeamMatch
from pydantic.dataclasses import dataclass
from sqlalchemy import Row, case, func, or_, select
from sqlalchemy.orm import Session


@dataclass
class PlayerWithRating:
    id: UUID
    name: str
    ranking: int | None
    history: list[dict] | None = None


@dataclass
class PlayerWinStats:
    wins: int
    matches_played: int


def list_players(con: Session) -> list[PlayerWithRating]:
    latest_rating_subq = (
        select(PlayerRating.rating)
        .join(Match, PlayerRating.match_id == Match.id)
        .where(Player.id == PlayerRating.player_id)
        .order_by(Match.created_at.desc(), Match.id.desc())
        .limit(1)
        .scalar_subquery()
    )

    stmt = select(Player, latest_rating_subq.label("latest_rating")).order_by(latest_rating_subq.desc().nullslast())
    result = con.execute(stmt)
    rows = result.fetchall()
    return [PlayerWithRating(id=row[0].id, name=row[0].name, ranking=row[1]) for row in rows]


def show_player(con: Session, player_id: UUID) -> PlayerWithRating | Sequence[Row[*tuple[Any, ...]]]:
    stmt = (
        select(
            Player.id,
            Player.name,
            Player.active,
            PlayerRating.rating,
            PlayerRating.created_at,
            Match.id.label("match_id"),
        )
        .select_from(Player)
        .join(PlayerRating, Player.id == PlayerRating.player_id, isouter=True)
        .join(Match, PlayerRating.match_id == Match.id, isouter=True)
        .where(Player.id == player_id)
        .order_by(Match.created_at.desc(), Match.id.desc())
        .limit(10)
    )

    result = con.execute(stmt)
    rows = result.fetchall()

    if rows == []:
        return rows

    history = []
    for row in rows:
        if row.rating is not None:
            history.append(
                {
                    "rating": row.rating,
                    "created_at": row.created_at,
                    "match_id": row.match_id,
                }
            )

    return PlayerWithRating(id=rows[0].id, name=rows[0].name, ranking=rows[0].rating, history=history)


def get_player_win_stats(con: Session, player_id: UUID) -> PlayerWinStats:
    player_match_results = (
        select(
            Match.id.label("match_id"),
            func.max(case((TeamMatch.team_id == Match.winning_team_id, 1), else_=0)).label("won"),
        )
        .join(TeamMatch, TeamMatch.match_id == Match.id)
        .join(Team, Team.id == TeamMatch.team_id)
        .where(or_(Team.team_player_1_id == player_id, Team.team_player_2_id == player_id))
        .group_by(Match.id)
        .subquery()
    )
    stmt = select(
        func.count(player_match_results.c.match_id),
        func.coalesce(func.sum(player_match_results.c.won), 0),
    )
    matches_played, wins = con.execute(stmt).one()
    return PlayerWinStats(wins=wins, matches_played=matches_played)


def count_player_ratings(con: Session, player_id: UUID) -> int:
    stmt = select(func.count()).select_from(PlayerRating).where(PlayerRating.player_id == player_id)
    result = con.execute(stmt)
    row = result.fetchone()
    return row[0] if row else 0


def get_player_ratings_page(con: Session, player_id: UUID, page: int, page_size: int = 10) -> list[dict]:
    safe_page = max(page, 1)
    offset = (safe_page - 1) * page_size

    stmt = (
        select(
            PlayerRating.rating,
            PlayerRating.created_at,
            Match.id.label("match_id"),
        )
        .select_from(PlayerRating)
        .join(Match, PlayerRating.match_id == Match.id, isouter=True)
        .where(PlayerRating.player_id == player_id)
        .order_by(Match.created_at.desc(), Match.id.desc())
        .offset(offset)
        .limit(page_size + 1)
    )

    rows = con.execute(stmt).fetchall()
    return [
        {
            "rating": row.rating,
            "created_at": row.created_at,
            "match_id": row.match_id,
        }
        for row in rows
    ]

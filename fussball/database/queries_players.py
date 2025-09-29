from uuid import UUID
from sqlalchemy import select, func, desc, union_all
from sqlalchemy.orm import aliased, Session
from fussball.database.tables import Player, PlayerRating, Match, Team
from fussball.database.dto import PlayerRatingInfo, MatchDetails
from pydantic.dataclasses import dataclass

@dataclass
class PlayerWithRating:
    id: UUID
    name: str
    ranking: int | None
    history: list[dict] = None

def list_players(con: Session) -> list[Player]:
    latest_rating_subq = (
        select(PlayerRating.rating)
        .where(Player.id == PlayerRating.player_id)
        .order_by(PlayerRating.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )

    stmt = select(Player, latest_rating_subq.label("latest_rating")).order_by(Player.name)
    result = con.execute(stmt)
    rows = result.fetchall()
    return [PlayerWithRating(id=row[0].id, name=row[0].name, ranking=row[1]) for row in rows]


def show_player(con: Session, player_id: UUID) -> Player:
    stmt = select(Player).where(Player.id == player_id).limit(1)
    result = con.execute(stmt)
    player = result.scalar_one_or_none()

    latest_rating_subq = (
        select(PlayerRating.rating)
        .where(Player.id == player_id)
        .order_by(PlayerRating.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )

    player_ratings_stmt = (
        select(PlayerRating)
        .where(Player.id == player_id)
        .limit(10)
        .order_by(PlayerRating.created_at.desc())
    )

    player_rating = PlayerWithRating(id=player.id, name=player.name, ranking=None)

    player_ratings = con.execute(player_ratings_stmt).fetchall()
    player.history = [dict(row) for row in player_ratings]
    return player
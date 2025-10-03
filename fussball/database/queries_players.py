from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from fussball.database.tables import Player, PlayerRating
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


def show_player(con: Session, player_id: UUID) -> PlayerWithRating:
    output = con.execute(
        text("""
            SELECT
                player.id,
                player.name,
                player.active,
                player_rating.rating,
                player_rating.created_at
            FROM player
            LEFT JOIN player_rating ON player.id = player_rating.player_id
            WHERE player.id = :player_id
            ORDER BY player_rating.created_at DESC
            LIMIT 10
        """),
        {"player_id": player_id},
    )
    rows = output.all()
    if not rows:
        raise ValueError(f"Player with id {player_id} not found")
    return PlayerWithRating(id=rows[0].id, name=rows[0].name, ranking=rows[0].rating, history=[dict(row._mapping) for row in rows])

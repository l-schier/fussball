from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.tables import Match, Player, PlayerRating
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

    stmt = select(Player, latest_rating_subq.label("latest_rating")).order_by(latest_rating_subq.desc().nullslast())
    result = con.execute(stmt)
    rows = result.fetchall()
    return [PlayerWithRating(id=row[0].id, name=row[0].name, ranking=row[1]) for row in rows]


def show_player(con: Session, player_id: UUID) -> PlayerWithRating:
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
        .order_by(PlayerRating.created_at.desc())
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

from dataclasses import dataclass
from uuid import UUID

from database.tables import Match, Player, Team, TeamMatch, TeamRating
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased


@dataclass(frozen=True)
class TeamRanking:
    team_id: UUID
    members: tuple[str, ...]
    rating: int | None
    rank: int | None


def list_team_rankings(con: Session) -> list[TeamRanking]:
    first_player = aliased(Player, name="first_player")
    second_player = aliased(Player, name="second_player")
    latest_rating = (
        select(TeamRating.rating)
        .select_from(TeamMatch)
        .join(Match, TeamMatch.match_id == Match.id)
        .outerjoin(TeamRating, TeamRating.team_match_id == TeamMatch.id)
        .where(TeamMatch.team_id == Team.id)
        .order_by(
            Match.created_at.desc(),
            Match.id.desc(),
            TeamRating.created_at.desc().nullslast(),
            TeamRating.id.desc().nullslast(),
        )
        .limit(1)
        .scalar_subquery()
    )
    statement = (
        select(Team.id, first_player.name, second_player.name, latest_rating.label("rating"))
        .join(first_player, Team.team_player_1_id == first_player.id)
        .join(second_player, Team.team_player_2_id == second_player.id, isouter=True)
    )

    rows = con.execute(statement).all()
    teams = [
        (
            team_id,
            tuple(
                sorted((name for name in (first_name, second_name) if name), key=lambda name: (name.casefold(), name))
            ),
            rating,
        )
        for team_id, first_name, second_name, rating in rows
    ]
    teams.sort(
        key=lambda team: (
            team[2] is None,
            -team[2] if team[2] is not None else 0,
            tuple(name.casefold() for name in team[1]),
            team[1],
            str(team[0]),
        )
    )

    rankings: list[TeamRanking] = []
    previous_rating: int | None = None
    previous_rank: int | None = None
    for position, (team_id, members, rating) in enumerate(teams, start=1):
        if rating is None:
            rank = None
        elif rating == previous_rating:
            rank = previous_rank
        else:
            rank = position
        rankings.append(TeamRanking(team_id=team_id, members=members, rating=rating, rank=rank))
        if rating is not None:
            previous_rating = rating
            previous_rank = rank

    return rankings

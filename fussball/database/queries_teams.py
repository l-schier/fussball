from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from database.tables import Match, Player, Team, TeamMatch, TeamRating
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, aliased


@dataclass(frozen=True)
class TeamRanking:
    team_id: UUID
    members: tuple[str, ...]
    rating: int | float | None
    rank: int | None


@dataclass(frozen=True)
class _TeamForRanking:
    team_id: UUID
    members: tuple[str, ...]
    rating: int | float | None


@dataclass(frozen=True)
class TeamDetails:
    team_id: UUID
    members: tuple[str, ...]


@dataclass(frozen=True)
class TeamMatchHistory:
    match_id: UUID
    played_at: datetime
    opponent_members: tuple[str, ...]
    team_score: int
    opponent_score: int
    won: bool
    rating: int | float | None


@dataclass(frozen=True)
class TeamWinStats:
    wins: int
    matches_played: int


def _ordered_member_names(first_name: str | None, second_name: str | None) -> tuple[str, ...]:
    return tuple(sorted((name for name in (first_name, second_name) if name), key=lambda name: (name.casefold(), name)))


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
        .join(second_player, Team.team_player_2_id == second_player.id)
    )

    rows = con.execute(statement).all()
    teams = [
        _TeamForRanking(
            team_id=team_id,
            members=_ordered_member_names(first_name, second_name),
            rating=rating,
        )
        for team_id, first_name, second_name, rating in rows
    ]
    teams.sort(
        key=lambda team: (
            team.rating is None,
            -team.rating if team.rating is not None else 0,
            tuple(name.casefold() for name in team.members),
            team.members,
            str(team.team_id),
        )
    )

    rankings: list[TeamRanking] = []
    previous_rating: int | float | None = None
    previous_rank: int | None = None
    for position, team in enumerate(teams, start=1):
        if team.rating is None:
            rank = None
        elif team.rating == previous_rating:
            rank = previous_rank
        else:
            rank = position
        rankings.append(TeamRanking(team_id=team.team_id, members=team.members, rating=team.rating, rank=rank))
        if team.rating is not None:
            previous_rating = team.rating
            previous_rank = rank

    return rankings


def get_team_details(con: Session, team_id: UUID) -> TeamDetails | None:
    first_player = aliased(Player, name="team_first_player")
    second_player = aliased(Player, name="team_second_player")
    statement = (
        select(
            Team.id.label("team_id"),
            first_player.name.label("first_name"),
            second_player.name.label("second_name"),
        )
        .join(first_player, Team.team_player_1_id == first_player.id)
        .outerjoin(second_player, Team.team_player_2_id == second_player.id)
        .where(Team.id == team_id)
    )
    row = con.execute(statement).one_or_none()
    if row is None:
        return None
    return TeamDetails(team_id=row.team_id, members=_ordered_member_names(row.first_name, row.second_name))


def get_team_win_stats(con: Session, team_id: UUID) -> TeamWinStats:
    team_match_results = (
        select(
            Match.id.label("match_id"),
            func.max(case((Match.winning_team_id == team_id, 1), else_=0)).label("won"),
        )
        .join(TeamMatch, TeamMatch.match_id == Match.id)
        .where(TeamMatch.team_id == team_id)
        .group_by(Match.id)
        .subquery()
    )
    statement = select(
        func.count(team_match_results.c.match_id),
        func.coalesce(func.sum(team_match_results.c.won), 0),
    )
    matches_played, wins = con.execute(statement).one()
    return TeamWinStats(wins=wins, matches_played=matches_played)


def count_team_matches(con: Session, team_id: UUID) -> int:
    statement = select(func.count()).select_from(TeamMatch).where(TeamMatch.team_id == team_id)
    return con.execute(statement).scalar_one()


def get_team_match_history_page(
    con: Session,
    team_id: UUID,
    page: int,
    page_size: int = 10,
) -> list[TeamMatchHistory]:
    opponent_team = aliased(Team, name="opponent_team")
    opponent_first_player = aliased(Player, name="opponent_first_player")
    opponent_second_player = aliased(Player, name="opponent_second_player")
    is_winning_team = Match.winning_team_id == team_id
    opponent_team_id = case((is_winning_team, Match.losing_team_id), else_=Match.winning_team_id)
    team_score = case((is_winning_team, Match.winning_team_score), else_=Match.losing_team_score)
    opponent_score = case((is_winning_team, Match.losing_team_score), else_=Match.winning_team_score)
    rating = (
        select(TeamRating.rating)
        .where(TeamRating.team_match_id == TeamMatch.id)
        .order_by(TeamRating.created_at.desc(), TeamRating.id.desc())
        .limit(1)
        .scalar_subquery()
    )
    statement = (
        select(
            Match.id.label("match_id"),
            Match.created_at.label("played_at"),
            opponent_first_player.name.label("opponent_first_name"),
            opponent_second_player.name.label("opponent_second_name"),
            team_score.label("team_score"),
            opponent_score.label("opponent_score"),
            is_winning_team.label("won"),
            rating.label("rating"),
        )
        .select_from(TeamMatch)
        .join(Match, TeamMatch.match_id == Match.id)
        .join(opponent_team, opponent_team.id == opponent_team_id)
        .join(opponent_first_player, opponent_team.team_player_1_id == opponent_first_player.id)
        .outerjoin(opponent_second_player, opponent_team.team_player_2_id == opponent_second_player.id)
        .where(TeamMatch.team_id == team_id)
        .order_by(Match.created_at.desc(), Match.id.desc())
        .offset((max(page, 1) - 1) * page_size)
        .limit(page_size)
    )
    return [
        TeamMatchHistory(
            match_id=row.match_id,
            played_at=row.played_at,
            opponent_members=_ordered_member_names(row.opponent_first_name, row.opponent_second_name),
            team_score=row.team_score,
            opponent_score=row.opponent_score,
            won=row.won,
            rating=row.rating,
        )
        for row in con.execute(statement)
    ]

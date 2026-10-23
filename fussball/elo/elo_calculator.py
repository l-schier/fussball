import math
import uuid
from datetime import UTC, datetime

from database.tables import Match, Team, TeamMatch
from elo.upload_match import MatchScores, UploadMatch, validate_match_scores
from sqlalchemy import select
from sqlalchemy.orm import Session


def calculate_point_factor(score_difference: int) -> float:
    return 2 + (math.log(score_difference + 1) / math.log(10)) ** 3


def get_or_create_team(player_1: uuid.UUID, player_2: uuid.UUID | None, conn: Session) -> Team:
    # Try to find the team using SQLAlchemy ORM
    team: Team = (
        (
            conn.execute(
                select(Team).filter(
                    ((Team.team_player_1_id == player_1) & (Team.team_player_2_id == player_2))
                    | ((Team.team_player_1_id == player_2) & (Team.team_player_2_id == player_1))
                )
            )
        )
        .scalars()
        .first()
    )
    if team is None:
        new_team = Team(
            id=uuid.uuid4(),
            team_player_1_id=player_1,
            team_player_2_id=player_2,
            created_at=datetime.now(tz=UTC),
        )
        conn.add(new_team)
        return new_team

    return team


def expected_score(player_rating: int, opponent_rating: list[int]):
    average_opponent_rating = 0
    for rating in opponent_rating:
        average_opponent_rating += 1 / (1 + 10 ** ((rating - player_rating) / 500))
    average_opponent_rating /= len(opponent_rating)

    return average_opponent_rating


def calculate_rating_player(
    games_played: int,
    match_result: MatchScores,
    player_rating: int,
    player_expected_score: float,
    team_actual_score: int,
) -> int:
    k_value = 50 / (1 + games_played / 300)
    point_factor = calculate_point_factor(abs(match_result.score_team_1 - match_result.score_team_2))
    new_rating = player_rating + k_value * point_factor * (team_actual_score - player_expected_score)
    return round(new_rating)


def calculate_rating_team(
    games_played: int,
    match_result: MatchScores,
    team_rating: float,
    team_expected_score: float,
    team_actual_score: int,
) -> float:
    k_value = 50 / (1 + games_played / 100)
    point_factor = calculate_point_factor(abs(match_result.score_team_1 - match_result.score_team_2))
    new_rating = team_rating + k_value * point_factor * (team_actual_score - team_expected_score)
    return new_rating


def process_game_data(match_result: UploadMatch, conn: Session) -> uuid.UUID:
    validate_match_scores(match_result.score_team_1, match_result.score_team_2)

    match_id = uuid.uuid4()
    with conn.begin():
        team_1 = get_or_create_team(match_result.player_1, match_result.player_2, conn)
        team_2 = get_or_create_team(match_result.player_3, match_result.player_4, conn)
        conn.flush()

        team_1_won = match_result.score_team_1 > match_result.score_team_2
        match = Match(
            id=match_id,
            created_at=match_result.date,
            winning_team_id=team_1.id if team_1_won else team_2.id,
            losing_team_id=team_2.id if team_1_won else team_1.id,
            winning_team_score=max(match_result.score_team_1, match_result.score_team_2),
            losing_team_score=min(match_result.score_team_1, match_result.score_team_2),
        )
        conn.add(match)
        conn.flush()

        conn.add_all(
            [
                TeamMatch(id=uuid.uuid4(), team_id=team_1.id, match_id=match.id, created_at=match_result.date),
                TeamMatch(id=uuid.uuid4(), team_id=team_2.id, match_id=match.id, created_at=match_result.date),
            ]
        )
        conn.flush()

        from elo.rating_replay import replay_rating_history

        replay_rating_history(conn)

    return match_id

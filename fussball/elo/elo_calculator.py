from datetime import datetime, timezone
import uuid
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session
import math
from elo.upload_match import UploadMatch
from database.tables import Match, PlayerRating, Team, TeamMatch, TeamRating


class GamesPlayed(BaseModel):
    player1_games: int
    player2_games: int
    player3_games: int
    player4_games: int


def calculate_point_factor(score_difference):
    return 2 + (math.log(score_difference + 1) / math.log(10)) ** 3


def get_team_ratings(team1_id: int, team2_id: int, conn: Session) -> tuple[int, int]:
    def get_team_rating(team_id: int) -> int:
        subquery = select(TeamMatch.id).where(TeamMatch.team_id == team_id)
        stmt = (
            select(TeamRating.rating, TeamRating.created_at)
            .where(TeamRating.team_match_id.in_(subquery))
            .order_by(desc(TeamRating.created_at))
            .limit(1)
        )
        result = conn.execute(stmt)
        return result.scalar() or 1500

    team1_rating = get_team_rating(team1_id)
    team2_rating = get_team_rating(team2_id)

    return team1_rating, team2_rating


def get_player_rating_by_id(player_id: int, conn: Session) -> int:
    stmt = select(PlayerRating.rating).where(PlayerRating.player_id == player_id).order_by(PlayerRating.created_at.desc()).limit(1)
    result = conn.execute(stmt)
    rating = result.scalar()
    if rating is None:
        return 1500
    return rating


def get_player_ratings(match_result: UploadMatch, conn: Session) -> tuple[int, int, int, int]:
    player1_rating = get_player_rating_by_id(match_result.player_1, conn)
    player2_rating = get_player_rating_by_id(match_result.player_2, conn) if match_result.player_2 is not None else None
    player3_rating = get_player_rating_by_id(match_result.player_3, conn)
    player4_rating = get_player_rating_by_id(match_result.player_4, conn) if match_result.player_4 is not None else None

    return player1_rating, player2_rating, player3_rating, player4_rating


def number_of_games_team(team1_id: int, team2_id: int, date, conn: Session) -> tuple[int, int]:
    def get_number_of_games_by_team(team_id: int, date, conn: Session) -> int:
        stmt = (
            select(func.count())
            .select_from(Match)
            .where(((Match.winning_team_id == team_id) | (Match.losing_team_id == team_id)) & (Match.created_at <= date))
        )
        result = conn.execute(stmt)
        number_of_game_team = result.scalar() or 0
        return number_of_game_team

    number_of_game_team_1 = get_number_of_games_by_team(team1_id, date, conn)
    number_of_game_team_2 = get_number_of_games_by_team(team2_id, date, conn)

    return (number_of_game_team_1, number_of_game_team_2)


def get_number_of_games_by_player(player_id: int, date: datetime, conn: Session) -> int:
    stmt = (
        select(func.count())
        .select_from(PlayerRating)
        .join(Match, PlayerRating.match_id == Match.id)
        .where((PlayerRating.player_id == player_id) & (Match.created_at <= date))
    )
    result = conn.execute(stmt)
    number_of_game_player = result.scalar() or 0
    return number_of_game_player


def number_of_games_player(match_result: UploadMatch, date: datetime, conn: Session) -> GamesPlayed:
    player1_games = get_number_of_games_by_player(match_result.player_1, date, conn)
    player2_games = get_number_of_games_by_player(match_result.player_2, date, conn)
    player3_games = get_number_of_games_by_player(match_result.player_3, date, conn)
    player4_games = get_number_of_games_by_player(match_result.player_4, date, conn)

    # Return the number of games played by each player as a tuple
    return GamesPlayed(
        player1_games=player1_games,
        player2_games=player2_games,
        player3_games=player3_games,
        player4_games=player4_games,
    )


def get_or_create_team(player_1: uuid.UUID, player_2: uuid.UUID, conn: Session) -> Team:
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
            created_at=datetime.now(tz=timezone.utc),
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
    match_result: UploadMatch,
    player_rating: int,
    player_expected_score: int,
    team_actual_score: int,
) -> int:
    k_value = 50 / (1 + games_played / 300)
    point_factor = calculate_point_factor(abs(match_result.score_team_1 - match_result.score_team_2))
    new_rating = player_rating + k_value * point_factor * (team_actual_score - player_expected_score)
    return round(new_rating)


def calculate_rating_team(
    games_played: int,
    match_result: UploadMatch,
    team_rating: int,
    team_expected_score: float,
    team_actual_score: int,
) -> int:
    k_value = 50 / (1 + games_played / 100)
    point_factor = calculate_point_factor(abs(match_result.score_team_1 - match_result.score_team_2))
    new_rating = team_rating + k_value * point_factor * (team_actual_score - team_expected_score)
    return new_rating


def process_game_data(match_result: UploadMatch, conn: Session) -> uuid.UUID:
    # Connect to the database

    print("date is", match_result.date)

    team_1 = get_or_create_team(match_result.player_1, match_result.player_2, conn)
    team_2 = get_or_create_team(match_result.player_3, match_result.player_4, conn)

    if match_result.score_team_1 == match_result.score_team_2:
        raise ValueError("A match cannot end in a draw")

    conn.commit()

    match = Match(
        id=uuid.uuid4(),
        created_at=match_result.date,
        winning_team_id=(team_1.id if match_result.score_team_1 > match_result.score_team_2 else team_2.id),
        losing_team_id=(team_2.id if match_result.score_team_1 > match_result.score_team_2 else team_1.id),
        winning_team_score=(
            match_result.score_team_1 if match_result.score_team_1 > match_result.score_team_2 else match_result.score_team_2
        ),
        losing_team_score=(
            match_result.score_team_2 if match_result.score_team_1 > match_result.score_team_2 else match_result.score_team_1
        ),
    )

    conn.add(match)

    tm_1 = TeamMatch(
        id=uuid.uuid4(),
        team_id=team_1.id,
        match_id=match.id,
        created_at=datetime.now(tz=timezone.utc),
    )
    tm_2 = TeamMatch(
        id=uuid.uuid4(),
        team_id=team_2.id,
        match_id=match.id,
        created_at=datetime.now(tz=timezone.utc),
    )
    conn.add(tm_1)
    conn.add(tm_2)

    conn.commit()

    # Call the number_of_games_player function inside the loop
    games_played = number_of_games_player(match_result, match_result.date, conn)

    # Call the number_of_games_team function inside the loop
    number_of_games_team1, number_of_games_team2 = number_of_games_team(
        team1_id=team_1.id, team2_id=team_2.id, date=match_result.date, conn=conn
    )

    # Call the get_player_ratings function inside the loop
    player1_rating, player2_rating, player3_rating, player4_rating = get_player_ratings(match_result, conn)

    player_ratings_versus_p12 = []
    player_ratings_versus_p12.append(player3_rating)
    if player4_rating is not None:
        player_ratings_versus_p12.append(player4_rating)

    player_ratings_versus_p34 = []
    player_ratings_versus_p34.append(player1_rating)
    if player2_rating is not None:
        player_ratings_versus_p34.append(player2_rating)

    # Call the get_teams_ratings function inside the loop
    team1_rating, team2_rating = get_team_ratings(team_1.id, team_2.id, conn)

    # Calculate the expected scores for the players
    t1_expected_rating = []
    player1_expected_score = expected_score(player1_rating, player_ratings_versus_p12)
    t1_expected_rating.append(player1_expected_score)
    player2_expected_score = None
    if player2_rating is not None:
        player2_expected_score = expected_score(player2_rating, player_ratings_versus_p12)
        t1_expected_rating.append(player2_expected_score)

    t2_expected_rating = []
    player3_expected_score = expected_score(player3_rating, player_ratings_versus_p34)
    t2_expected_rating.append(player3_expected_score)
    player4_expected_score = None
    if player4_rating is not None:
        player4_expected_score = expected_score(player4_rating, player_ratings_versus_p34)
        t2_expected_rating.append(player4_expected_score)

    # Calculate the expected scores for the teams
    team1_expected_score = sum(t1_expected_rating) / len(t1_expected_rating)
    team2_expected_score = sum(t2_expected_rating) / len(t2_expected_rating)

    team1_actual_score = 1 if match_result.score_team_1 > match_result.score_team_2 else 0
    team2_actual_score = 1 if match_result.score_team_2 > match_result.score_team_1 else 0

    # Calculate the new Elo ratings for each player
    player1_new_rating = calculate_rating_player(
        games_played.player1_games,
        match_result,
        player1_rating,
        player1_expected_score,
        team1_actual_score,
    )
    player2_new_rating = None
    if player2_rating is not None:
        player2_new_rating = calculate_rating_player(
            games_played.player2_games,
            match_result,
            player2_rating,
            player2_expected_score,
            team1_actual_score,
        )
    player3_new_rating = calculate_rating_player(
        games_played.player3_games,
        match_result,
        player3_rating,
        player3_expected_score,
        team2_actual_score,
    )
    player4_new_rating = None
    if player4_rating is not None:
        player4_new_rating = calculate_rating_player(
            games_played.player4_games,
            match_result,
            player4_rating,
            player4_expected_score,
            team2_actual_score,
        )

    # Calculate the new Elo ratings for each team
    team1_new_rating = calculate_rating_team(
        number_of_games_team1,
        match_result,
        team1_rating,
        team1_expected_score,
        team1_actual_score,
    )
    team2_new_rating = calculate_rating_team(
        number_of_games_team2,
        match_result,
        team2_rating,
        team2_expected_score,
        team2_actual_score,
    )
    # Log the new ratings for teams

    player_ratings = [
        PlayerRating(
            id=uuid.uuid4(),
            match_id=match.id,
            player_id=match_result.player_1,
            rating=player1_new_rating,
            created_at=match_result.date,
        ),
        PlayerRating(
            id=uuid.uuid4(),
            match_id=match.id,
            player_id=match_result.player_3,
            rating=player3_new_rating,
            created_at=match_result.date,
        ),
    ]
    if player2_rating is not None:
        player_ratings.append(
            PlayerRating(
                id=uuid.uuid4(),
                match_id=match.id,
                player_id=match_result.player_2,
                rating=player2_new_rating,
                created_at=match_result.date,
            )
        )
    if player4_rating is not None:
        player_ratings.append(
            PlayerRating(
                id=uuid.uuid4(),
                match_id=match.id,
                player_id=match_result.player_4,
                rating=player4_new_rating,
                created_at=match_result.date,
            )
        )

    # Update the database with the player ratings
    conn.add_all(player_ratings)

    for pr in player_ratings:
        print(f"PlayerMatch ID: {pr.match_id}, New Rating: {pr.rating}")

    # Update the database with the team ratings
    conn.add_all(
        [
            TeamRating(
                id=uuid.uuid4(),
                team_match_id=tm_1.id,
                rating=team1_new_rating,
                created_at=match_result.date,
            ),
            TeamRating(
                id=uuid.uuid4(),
                team_match_id=tm_2.id,
                rating=team2_new_rating,
                created_at=match_result.date,
            ),
        ]
    )

    conn.commit()
    return match.id

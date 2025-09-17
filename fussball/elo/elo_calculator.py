import uuid
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
import math
from fussball.elo.upload_match import UploadMatch
from fussball.database.tables import Match, PlayerMatch, PlayerRating, Team, TeamMatch, TeamRating

class GamesPlayed(BaseModel):
    player1_games: int
    player2_games: int
    player3_games: int
    player4_games: int

def calculate_point_factor(score_difference):
    return 2 + (math.log(score_difference + 1) / math.log(10)) ** 3

async def get_team_ratings(team1_id: int, team2_id: int, conn: AsyncSession) -> tuple[int, int]:
    async def get_team_rating(team_id: int) -> int:
        subquery = select(TeamMatch.id).where(TeamMatch.team_id == team_id)
        stmt = (
            select(TeamRating.rating, TeamRating.created_at)
            .where(TeamRating.team_match_id.in_(subquery))
            .order_by(desc(TeamRating.created_at))
            .limit(1)
        )
        result = await conn.execute(stmt)
        return result.scalar() or 1500

    team1_rating = await get_team_rating(team1_id)
    team2_rating = await get_team_rating(team2_id)

    return team1_rating, team2_rating


async def get_player_rating_by_id(player_id: int, conn: AsyncSession) -> int:
    stmt = (
        select(PlayerRating.rating)
        .join(PlayerMatch, PlayerRating.player_match_id == PlayerMatch.id)
        .where(PlayerMatch.player_id == player_id)
        .order_by(PlayerRating.created_at.desc())
        .limit(1)
    )
    result = await conn.execute(stmt)
    rating = result.scalar()
    if rating is None:
        return 1500
    return rating


async def get_player_ratings(match_result: UploadMatch, conn: AsyncSession) -> tuple[int, int, int, int]:
    player1_rating = await get_player_rating_by_id(match_result.player_1, conn)
    player2_rating = await get_player_rating_by_id(match_result.player_2, conn)
    player3_rating = await get_player_rating_by_id(match_result.player_3, conn)
    player4_rating = await get_player_rating_by_id(match_result.player_4, conn)

    return player1_rating, player2_rating, player3_rating, player4_rating

async def number_of_games_team(team1_id: int, team2_id: int ,date, conn: AsyncSession) -> tuple[int, int]:
    async def get_number_of_games_by_team(team_id: int, date, conn: AsyncSession) -> int:
        stmt = select(func.count()).select_from(Match).where(
            ((Match.winning_team_id == team_id) | (Match.losing_team_id == team_id)) & (Match.created_at <= date)
        )
        result = await conn.execute(stmt)
        number_of_game_team = result.scalar() or 0
        return number_of_game_team
    
    number_of_game_team_1 = await get_number_of_games_by_team(team1_id, date, conn)
    number_of_game_team_2 = await get_number_of_games_by_team(team2_id, date, conn)

    return (number_of_game_team_1, number_of_game_team_2)

async def get_number_of_games_by_player(player_id: int, date, conn: AsyncSession) -> int:
        stmt = select(func.count()).select_from(PlayerMatch).join(Match, PlayerMatch.match_id == Match.id).where(
            (PlayerMatch.player_id == player_id) & (Match.created_at <= date)
        )
        result = await conn.execute(stmt)
        number_of_game_player = result.scalar() or 0
        return number_of_game_player

async def number_of_games_player(match_result: UploadMatch, date, conn: AsyncSession) -> GamesPlayed:
    player1_games = await get_number_of_games_by_player(match_result.player_1, date, conn)
    player2_games = await get_number_of_games_by_player(match_result.player_2, date, conn)
    player3_games = await get_number_of_games_by_player(match_result.player_3, date, conn)
    player4_games = await get_number_of_games_by_player(match_result.player_4, date, conn)

    # Return the number of games played by each player as a tuple
    return GamesPlayed(player1_games=player1_games, player2_games=player2_games, player3_games=player3_games, player4_games=player4_games)


async def get_or_create_team(player_1: str, player_2: str, conn: AsyncSession) -> Team:
    # Try to find the team using SQLAlchemy ORM
    team: Team = (await conn.execute(select(Team).filter(
        ((Team.team_player_1_id == uuid.UUID(player_1)) & (Team.team_player_2_id == uuid.UUID(player_2))) |
        ((Team.team_player_1_id == uuid.UUID(player_2)) & (Team.team_player_2_id == uuid.UUID(player_1)))
    ))).scalars().first()
    if team is None:
        new_team = Team(team_player_1_id=player_1, team_player_2_id=player_2)
        conn.add(new_team)
        return new_team
    
    return team

async def process_game_data(match_result: UploadMatch, conn: AsyncSession):
    # Connect to the database

    print("date is", match_result.date)

    team_1 = await get_or_create_team(match_result.player_1, match_result.player_2, conn)
    team_2 = await get_or_create_team(match_result.player_3, match_result.player_4, conn)

    if match_result.score_team_1 == match_result.score_team_2:
        raise ValueError("A match cannot end in a draw")

    match = Match(
        id=uuid.uuid4(),
        created_at=match_result.date,
        winning_team_id=team_1.id if match_result.score_team_1 > match_result.score_team_2 else team_2.id,
        losing_team_id=team_2.id if match_result.score_team_1 > match_result.score_team_2 else team_1.id,
        winning_team_score=match_result.score_team_1 if match_result.score_team_1 > match_result.score_team_2 else match_result.score_team_2,
        losing_team_score=match_result.score_team_2 if match_result.score_team_1 > match_result.score_team_2 else match_result.score_team_1,
    )

    conn.add(match)
    player_match_p1 = PlayerMatch(id=uuid.uuid4(), player_id=match_result.player_1, match_id=match.id)
    player_match_p2 = PlayerMatch(id=uuid.uuid4(), player_id=match_result.player_2, match_id=match.id)
    player_match_p3 = PlayerMatch(id=uuid.uuid4(), player_id=match_result.player_3, match_id=match.id)
    player_match_p4 = PlayerMatch(id=uuid.uuid4(), player_id=match_result.player_4, match_id=match.id)

    conn.add(player_match_p1)
    conn.add(player_match_p2)
    conn.add(player_match_p3)
    conn.add(player_match_p4)

    tm_1 = TeamMatch(id=uuid.uuid4(), team_id=team_1.id, match_id=match.id)
    tm_2 = TeamMatch(id=uuid.uuid4(), team_id=team_2.id, match_id=match.id)
    conn.add(tm_1)
    conn.add(tm_2)

    await conn.commit()

    # Call the number_of_games_player function inside the loop
    games_played = await number_of_games_player(match_result, match_result.date, conn)

    # Call the number_of_games_team function inside the loop
    number_of_games_team1, number_of_games_team2 = await number_of_games_team(team1_id=team_1.id, team2_id=team_2.id, date=match_result.date, conn=conn)

    # Call the get_player_ratings function inside the loop
    player1_rating, player2_rating, player3_rating, player4_rating = await get_player_ratings(match_result, conn)

    # Call the get_teams_ratings function inside the loop
    team1_rating, team2_rating = await get_team_ratings(team_1.id, team_2.id, conn)

    # Calculate the expected scores for the players
    player1_expected_score_against_player3 = 1 / (1 + 10**((player3_rating - player1_rating) / 500))
    player1_expected_score_against_player4 = 1 / (1 + 10**((player4_rating - player1_rating) / 500))
    player1_expected_score = (player1_expected_score_against_player3 + player1_expected_score_against_player4) / 2
   
    player2_expected_score_against_player3 = 1 / (1 + 10**((player3_rating - player2_rating) / 500))
    player2_expected_score_against_player4 = 1 / (1 + 10**((player4_rating - player2_rating) / 500))
    player2_expected_score = (player2_expected_score_against_player3 + player2_expected_score_against_player4) / 2
   

    player3_expected_score_against_player1 = 1 / (1 + 10**((player1_rating - player3_rating) / 500))
    player3_expected_score_against_player2 = 1 / (1 + 10**((player2_rating - player3_rating) / 500))
    player3_expected_score = (player3_expected_score_against_player1 + player3_expected_score_against_player2) / 2
   

    player4_expected_score_against_player1 = 1 / (1 + 10**((player1_rating - player4_rating) / 500))
    player4_expected_score_against_player2 = 1 / (1 + 10**((player2_rating - player4_rating) / 500))
    player4_expected_score = (player4_expected_score_against_player1 + player4_expected_score_against_player2) / 2
   

    # Calculate the expected scores for the teams
    team1_expected_score = (player1_expected_score + player2_expected_score) / 2
    team2_expected_score = (player3_expected_score + player4_expected_score) / 2

    # Calculate the point factor to be used as a variable
    score_difference = abs(match_result.score_team_1 - match_result.score_team_2)
    point_factor = calculate_point_factor(score_difference)
   
    # Calculate the K value for each player based on the number of games played and their rating

    k1 = 50 / (1 + games_played.player1_games / 300)
    k2 = 50 / (1 + games_played.player2_games / 300)
    k3 = 50 / (1 + games_played.player3_games / 300)
    k4 = 50 / (1 + games_played.player4_games / 300)

    #delta = 32 * (1 - winnerChanceToWin)

    # Calculate the K value for each team based on the number of games played
    k5 = 50 / (1 + number_of_games_team1/ 100)
    k6 = 50 / (1 + number_of_games_team2/ 100)

    #logg the wining team

    team1_actual_score = 1 if match_result.score_team_1 > match_result.score_team_2 else 0
    team2_actual_score = 1 if match_result.score_team_2 > match_result.score_team_1 else 0
       
    # Calculate the new Elo ratings for each player
    
    player1_new_rating = player1_rating + k1 * point_factor  * (team1_actual_score - player1_expected_score)
    player2_new_rating = player2_rating + k2 * point_factor  * (team1_actual_score - player2_expected_score)
    player3_new_rating = player3_rating + k3 * point_factor  * (team2_actual_score - player3_expected_score)
    player4_new_rating = player4_rating + k4 * point_factor  * (team2_actual_score - player4_expected_score)


    # Calculate the new Elo ratings for each team
    team1_new_rating = team1_rating + k5 * point_factor * (team1_actual_score - team1_expected_score)
    team2_new_rating = team2_rating + k6 * point_factor * (team2_actual_score - team2_expected_score)
    # Log the new ratings for teams

    # Update the database with the player ratings
    conn.add_all([
        PlayerRating(id=uuid.uuid4(), player_match_id=player_match_p1, rating=player1_new_rating, created_at=match_result.date),
        PlayerRating(id=uuid.uuid4(), player_match_id=player_match_p2, rating=player2_new_rating, created_at=match_result.date),
        PlayerRating(id=uuid.uuid4(), player_match_id=player_match_p3, rating=player3_new_rating, created_at=match_result.date),
        PlayerRating(id=uuid.uuid4(), player_match_id=player_match_p4, rating=player4_new_rating, created_at=match_result.date)
    ])

    # Update the database with the team ratings
    conn.add_all([
        TeamRating(id=uuid.uuid4(), team_match_id=tm_1.id, rating=team1_new_rating, created_at=match_result.date),
        TeamRating(id=uuid.uuid4(), team_match_id=tm_2.id, rating=team2_new_rating, created_at=match_result.date)
    ])

    conn.commit()
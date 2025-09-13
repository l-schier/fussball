from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
import math

class MatchResult(BaseModel):
    player1_name: str
    player2_name: str
    team1_score: int
    player3_name: str
    player4_name: str
    team2_score: int
    date: datetime

class Players(BaseModel):
    player1_id: int
    player2_id: int
    player3_id: int
    player4_id: int

class GamesPlayed(BaseModel):
    player1_games: int
    player2_games: int
    player3_games: int
    player4_games: int

def calculate_point_factor(score_difference):
    return 2 + (math.log(score_difference + 1) / math.log(10)) ** 3

def get_team_match_id_by_timestamp_and_by_team_id(team1_id: int,team2_id: int, date: datetime, conn: Session) -> tuple[int, int]:
    result = conn.execute(text("SELECT TeamMatch.team_match_id FROM Match JOIN TeamMatch ON Match.match_id = TeamMatch.match_id WHERE TeamMatch.team_id = :team1_id AND Match.match_timestamp = :date;", {"team1_id": team1_id, "date": date}))
    team_match1_id = result.fetchone()[0]

    result = conn.execute(text("SELECT TeamMatch.team_match_id FROM Match JOIN TeamMatch ON Match.match_id = TeamMatch.match_id WHERE TeamMatch.team_id = :team2_id AND Match.match_timestamp = :date;", {"team2_id": team2_id, "date": date}))
    team_match2_id = result.fetchone()[0]

    return (team_match1_id,team_match2_id)

def get_player_match_id_by_timestamp_and_by_player_id(players: Players, date, conn: Session) -> tuple[int, int, int, int]:
    res = conn.execute(text("SELECT PlayerMatch.player_match_id FROM Match JOIN PlayerMatch ON Match.match_id = PlayerMatch.match_id WHERE PlayerMatch.player_id = :player1_id AND Match.match_timestamp = :date;", {"player1_id": players.player1_id, "date": date}))
    player1_match_id = res.fetchone()[0]

    res = conn.execute(text("SELECT PlayerMatch.player_match_id FROM Match JOIN PlayerMatch ON Match.match_id = PlayerMatch.match_id WHERE PlayerMatch.player_id = :player2_id AND Match.match_timestamp = :date;", {"player2_id": players.player2_id, "date": date}))
    player2_match_id = res.fetchone()[0]

    res = conn.execute(text("SELECT PlayerMatch.player_match_id FROM Match JOIN PlayerMatch ON Match.match_id = PlayerMatch.match_id WHERE PlayerMatch.player_id = :player3_id AND Match.match_timestamp = :date;", {"player3_id": players.player3_id, "date": date}))
    player3_match_id = res.fetchone()[0]

    res = conn.execute(text("SELECT PlayerMatch.player_match_id FROM Match JOIN PlayerMatch ON Match.match_id = PlayerMatch.match_id WHERE PlayerMatch.player_id = :player4_id AND Match.match_timestamp = :date;", {"player4_id": players.player4_id, "date": date}))
    player4_match_id = res.fetchone()[0]

    return (player1_match_id, player2_match_id, player3_match_id, player4_match_id)

def get_team_ratings(team1_id: int, team2_id: int, conn: Session) -> tuple[int, int]:
    conn.execute(text("SELECT rating, team_rating_timestamp FROM teamrating WHERE team_match_id IN (SELECT team_match_id FROM teammatch WHERE team_id = :team1_id) ORDER BY team_rating_timestamp DESC LIMIT 1;", {"team1_id": team1_id}))
    result = conn.fetchone()

    if result is not None:
        team1_rating = result[0]
    else:
     team1_rating = 1500

    conn.execute(text("SELECT rating, team_rating_timestamp FROM teamrating WHERE team_match_id IN (SELECT team_match_id FROM teammatch WHERE team_id = :team2_id) ORDER BY team_rating_timestamp DESC LIMIT 1;", {"team2_id": team2_id}))
    result = conn.fetchone()
    if result is not None:
        team2_rating = result[0]
    else:
     team2_rating = 1500

    return team1_rating, team2_rating


def get_player_rating_by_id(player_id: int, conn: Session) -> int:
    res = conn.execute(text("SELECT rating FROM playerrating WHERE player_match_id IN (SELECT player_match_id FROM playermatch WHERE player_id =:player_id) ORDER BY player_rating_timestamp DESC LIMIT 1"), {"player_id": player_id})
    rating = res.fetchone()
    if rating is None:
        return 1500
    return rating[0]


def get_player_ratings(players: Players, conn: Session) -> tuple[int, int, int, int]:
    player1_rating = get_player_rating_by_id(players.player1_id, conn)
    player2_rating = get_player_rating_by_id(players.player2_id, conn)
    player3_rating = get_player_rating_by_id(players.player3_id, conn)
    player4_rating = get_player_rating_by_id(players.player4_id, conn)

    return player1_rating, player2_rating, player3_rating, player4_rating

def number_of_games_team(team1_id: int, team2_id: int ,date, conn: Session) -> tuple[int, int]:
    res = conn.execute("SELECT COUNT(*) FROM Match WHERE (winning_team_id =%s OR losing_team_id = %s ) AND match_timestamp <=%s", (team1_id,team1_id,date))
    number_of_game_team_1 = res.fetchone()[0] or 0

    res = conn.execute("SELECT COUNT(*) FROM Match WHERE (winning_team_id =%s OR losing_team_id = %s ) AND match_timestamp <=%s", (team2_id,team2_id,date))
    number_of_game_team_2 = res.fetchone()[0] or 0

     # Return the number of games played by each team as a tuple
    return (number_of_game_team_1, number_of_game_team_2)

def get_number_of_games_by_player(player_id: int, date, conn: Session) -> int:
    res = conn.execute(text("SELECT COUNT(*) FROM PlayerMatch pm  INNER JOIN Match m ON pm.match_id = m.match_id  WHERE pm.player_id =:player_id AND m.match_timestamp <=:date"), {"player_id": player_id, "date": date})
    number_of_game_player = res.fetchone()[0] or 0
    return number_of_game_player

def number_of_games_player(players: Players, date, conn: Session) -> GamesPlayed:
    player1_games = get_number_of_games_by_player(players.player1_id, date, conn)
    player2_games = get_number_of_games_by_player(players.player2_id, date, conn)
    player3_games = get_number_of_games_by_player(players.player3_id, date, conn)
    player4_games = get_number_of_games_by_player(players.player4_id, date, conn)

    # Return the number of games played by each player as a tuple
    return GamesPlayed(player1_games=player1_games, player2_games=player2_games, player3_games=player3_games, player4_games=player4_games)

def _simple_insert_team_or_get_team_id(player1_id:int, player2_id:int, conn: Session):
     # Check if the team already exists
    res = conn.execute(text("SELECT team_id FROM team WHERE (team_player_1_id=:player1_id AND team_player_2_id=:player2_id) OR (team_player_1_id=:player2_id AND team_player_2_id=:player1_id)"), {"player1_id": player1_id, "player2_id": player2_id})
    team_id = res.fetchone()
    if team_id is None:
        # If the team does not exist, insert them into the teams table with a unique id
        res = conn.execute(text("SELECT nextval('team_id_seq')"))
        id = res.fetchone()[0]
        conn.execute(text("INSERT INTO team (team_id, team_player_1_id, team_player_2_id) VALUES (:id, :player1_id, :player2_id)"), {"id": id, "player1_id": player1_id, "player2_id": player2_id})
        team_id = id
    else:
        # If the team already exists, retrieve their id
        team_id = team_id[0]
    return team_id

def insert_team_or_get_team_id(players: Players, conn: Session):
    team1_id = _simple_insert_team_or_get_team_id(players.player1_id, players.player2_id, conn)
    team2_id = _simple_insert_team_or_get_team_id(players.player3_id, players.player4_id, conn)
    return (team1_id, team2_id)

def get_player_id_by_name(player_name: str, conn: Session) -> int:
    res = conn.execute(text("SELECT player_id FROM player WHERE first_name=:name"), {"name": player_name})
    player_id = res.fetchone()
    if player_id is None:
        return None
    return player_id[0]

# Get the player ID of the players playing a match
def get_player_id(match_result: MatchResult, conn: Session) -> Players:
    player1_id = get_player_id_by_name(match_result.player1_name, conn)
    player2_id = get_player_id_by_name(match_result.player2_name, conn)
    player3_id = get_player_id_by_name(match_result.player3_name, conn)
    player4_id = get_player_id_by_name(match_result.player4_name, conn)

    return Players(player1_id=player1_id, player2_id=player2_id, player3_id=player3_id, player4_id=player4_id)

def check_and_get_team_from_names(players: Players, conn: Session) -> tuple[int, int]:
    result = conn.execute(text("SELECT team_id FROM team WHERE (team_player_1_id=:player1_id AND team_player_2_id=:player2_id) OR (team_player_1_id=:player2_id AND team_player_2_id=:player1_id)"), {"player1_id": players.player1_id, "player2_id": players.player2_id})
    team_player_1_id = result.fetchone()
    if team_player_1_id is None:
        # If the team does not exist, insert them into the teams table with a unique id
        result = conn.execute(text("SELECT nextval('team_id_seq')"))
        id = result.fetchone()[0]
        conn.execute(text("INSERT INTO team (team_id, team_player_1_id, team_player_2_id) VALUES (:id, :player1_id, :player2_id)"), {"id": id, "player1_id": players.player1_id, "player2_id": players.player2_id})
        team_player_1_id = id
    else:
        # If the team already exists, retrieve their id
        team_player_1_id = team_player_1_id[0]
    return team_player_1_id

def process_game_data(match_result: MatchResult, conn: Session):
    # Connect to the database

    print("date is", match_result.date)

    players = get_player_id(match_result, conn)

    team_player_1_id = check_and_get_team_from_names(Players(player1_id=players.player1_id, player2_id=players.player2_id, player3_id=None, player4_id=None), conn)
    team_player_2_id = check_and_get_team_from_names(Players(player1_id=players.player3_id, player2_id=players.player4_id, player3_id=None, player4_id=None), conn)

    # Function to check winning team
    def get_winning_team(team1_score, team2_score):
      if team1_score > team2_score:
          return 1
      elif team2_score > team1_score:
          return 2
      else:
          return 0  

    # Insert the game into the matches table
    winning_team = get_winning_team(match_result.team1_score, match_result.team2_score)

    if winning_team == 1:
        winning_team_id = team_player_1_id
        losing_team_id = team_player_2_id
        winning_team_score = match_result.team1_score
        losing_team_score = match_result.team2_score
    elif winning_team == 2:
        winning_team_id = team_player_2_id
        losing_team_id = team_player_1_id
        winning_team_score = match_result.team2_score
        losing_team_score = match_result.team1_score
    else:
        winning_team_id = None
        losing_team_id = None
        winning_team_score = None
        losing_team_score = None  

    result = conn.execute(text("SELECT * FROM match WHERE match_timestamp=:date AND winning_team_id=:winning_team_id AND losing_team_id=:losing_team_id AND winning_team_score=:winning_team_score AND losing_team_score=:losing_team_score"), {"date": match_result.date, "winning_team_id": winning_team_id, "losing_team_id": losing_team_id, "winning_team_score": winning_team_score, "losing_team_score": losing_team_score})
    match = result.fetchone()
    if match is None:
        conn.execute(text("INSERT INTO match (match_timestamp, winning_team_id, losing_team_id, winning_team_score, losing_team_score) VALUES (:date, :winning_team_id, :losing_team_id, :winning_team_score, :losing_team_score)"), {"date": match_result.date, "winning_team_id": winning_team_id, "losing_team_id": losing_team_id, "winning_team_score": winning_team_score, "losing_team_score": losing_team_score})
        print(f'processing match: {match_result}')
        conn.commit()

        # get the last of the matches
        result = conn.execute(text("SELECT match_id FROM match ORDER BY match_id DESC LIMIT 1"))
        match_id = result.fetchone()[0]

        # Insert the players into the PlayerMatch table
        conn.execute(text("INSERT INTO PlayerMatch (player_id,match_id) VALUES (:player1_id, :match_id)"), {"player1_id": players.player1_id, "match_id": match_id})
        conn.execute(text("INSERT INTO PlayerMatch (player_id,match_id) VALUES (:player2_id, :match_id)"), {"player2_id": players.player2_id, "match_id": match_id})
        conn.execute(text("INSERT INTO PlayerMatch (player_id,match_id) VALUES (:player3_id, :match_id)"), {"player3_id": players.player3_id, "match_id": match_id})
        conn.execute(text("INSERT INTO PlayerMatch (player_id,match_id) VALUES (:player4_id, :match_id)"), {"player4_id": players.player4_id, "match_id": match_id})

        # Insert the team into the TeamMatch table
        conn.execute(text("INSERT INTO TeamMatch (team_id,match_id) VALUES (:team_id, :match_id)"), {"team_id": winning_team_id, "match_id": match_id})
        conn.execute(text("INSERT INTO TeamMatch (team_id,match_id) VALUES (:team_id, :match_id)"), {"team_id": losing_team_id, "match_id": match_id})

    else:
        print(f'Skipping match: {match_result} the match already exist')


# Call the get_player_id function inside the loop
    

    # Call the insert_team_or_get_team_id function inside the loop
    team1_id, team2_id = insert_team_or_get_team_id(players, conn)

    # Call the number_of_games_player function inside the loop
    games_played = number_of_games_player(players, match_result.date, conn)

    # Call the number_of_games_team function inside the loop
    number_of_games_team1, number_of_games_team2 = number_of_games_team(team1_id, team2_id, match_result.date, conn)

    # Call the get_player_ratings function inside the loop
    player1_rating, player2_rating, player3_rating, player4_rating = get_player_ratings(players, conn)

    # Call the get_teams_ratings function inside the loop
    team1_rating, team2_rating = get_team_ratings(team1_id, team2_id, conn)

    # Call the get_player_match_id_by_timestamp_and_by_player_id function inside the loop
    player_match1_id, player_match2_id, player_match3_id, player_match4_id  = get_player_match_id_by_timestamp_and_by_player_id(players, match_result.date, conn)

    # Call the get_team_match_id_by_timestamp_and_by_team_id function inside the loop
    team_match1_id, team_match2_id  = get_team_match_id_by_timestamp_and_by_team_id(team1_id, team2_id, match_result.date, conn)

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
   
    #input("Press enter to continue...")

    # Calculate the expected scores for the teams
    team1_expected_score = (player1_expected_score + player2_expected_score) / 2
    team2_expected_score = (player3_expected_score + player4_expected_score) / 2

   
    #input("Press enter to continue...")



    # Calculate the point factor to be used as a variable
    score_difference = abs(match_result.team1_score - match_result.team2_score)
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
    if match_result.team1_score > match_result.team2_score:
        team1_actual_score = 1
        team2_actual_score = 0

    else:
        team1_actual_score = 0
        team2_actual_score = 1
       
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
    print("Inserting player rating for player 1 with match ID", player_match1_id, "and new rating", player1_new_rating)
    conn.execute("INSERT INTO playerrating (player_match_id, rating, player_rating_timestamp) VALUES (%s, %s, %s)", (player_match1_id, player1_new_rating, match_result.date))

    print("Inserting player rating for player 2 with match ID", player_match2_id, "and new rating", player2_new_rating)
    conn.execute("INSERT INTO playerrating (player_match_id, rating, player_rating_timestamp) VALUES ( %s, %s, %s)", (player_match2_id, player2_new_rating, match_result.date))

    print("Inserting player rating for player 3 with match ID", player_match3_id, "and new rating", player3_new_rating)
    conn.execute("INSERT INTO playerrating (player_match_id,rating, player_rating_timestamp) VALUES (%s, %s, %s)", (player_match3_id,player3_new_rating, match_result.date))

    print("Inserting player rating for player 4 with match ID", player_match4_id, "and new rating", player4_new_rating)
    conn.execute("INSERT INTO playerrating (player_match_id, rating, player_rating_timestamp) VALUES (%s, %s, %s)", (player_match4_id, player4_new_rating, match_result.date))

    conn.commit()

    # Update the database with the team ratings
    conn.execute("INSERT INTO teamrating (team_match_id, rating, team_rating_timestamp) VALUES (%s, %s, %s)", (team_match1_id, team1_new_rating, match_result.date))
    conn.execute("INSERT INTO teamrating (team_match_id, rating, team_rating_timestamp) VALUES (%s, %s, %s)", (team_match2_id, team2_new_rating, match_result.date))

    conn.commit()
from uiwiz import ui
from fussball.database.dto import MatchDetails, PlayerRatingInfo
from sqlalchemy.orm import Session

from fussball.database.queries import get_match_details, get_player_ratings_after_match, list_matches

def render_match_from_id(match_id: str, con: Session):
    match_details = get_match_details(con, match_id)
    player_ratings: list[PlayerRatingInfo] = get_player_ratings_after_match(con, match_id)
    
    render_match(match_details, player_ratings)

def render_match(match_details: MatchDetails, player_ratings: list[PlayerRatingInfo]):
    ui.element("h2", "Match Details")
    ui.element("p", f"Match ID: {match_details.matchid}")
    ui.element("p", f"Created At: {match_details.created_at}")
    ui.element("p", f"Team 1 Score: {match_details.team1_score}")
    ui.element("p", f"Team 2 Score: {match_details.team2_score}")
    ui.table(player_ratings)

def render_match_list(con: Session):
    matches = list_matches(con, limit=10)
    ui.table(matches)

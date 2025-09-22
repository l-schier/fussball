from uiwiz import ui
from fussball.database.dto import MatchDetails, PlayerRatingInfo


def render_match(match_details: MatchDetails, player_ratings: list[PlayerRatingInfo]):
    ui.element("h2", "Match Details")
    ui.element("p", f"Match ID: {match_details.matchid}")
    ui.element("p", f"Created At: {match_details.created_at}")
    ui.element("p", f"Team 1 Score: {match_details.team1_score}")
    ui.element("p", f"Team 2 Score: {match_details.team2_score}")
    ui.table(player_ratings)
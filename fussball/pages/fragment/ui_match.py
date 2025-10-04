from uiwiz import ui
from sqlalchemy.orm import Session
from fussball.database.dto import MatchDetails, PlayerRatingInfo
from fussball.pages.routes import routes

from fussball.database.queries import get_match_details, get_player_ratings_after_match, list_matches
from fussball.pages.fragment.arrow import render_rating_diff

def render_match_from_id(match_id: str, con: Session):
    match_details = get_match_details(con, match_id)
    player_ratings: list[PlayerRatingInfo] = get_player_ratings_after_match(con, match_id)

    render_match(match_details, player_ratings)

def render_match(match_details: MatchDetails, player_ratings: list[PlayerRatingInfo]):
    ui.element("h2", "Match Details")
    ui.element("p", f"Match ID: {match_details.matchid}")
    ui.element("p", f"Created At: {match_details.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    ui.element("p", f"Team 1 Score: {match_details.team1_score}")
    ui.element("p", f"Team 2 Score: {match_details.team2_score}")

    with ui.element("table").classes("table table-zebra table-auto bg-base-300 overflow-scroll w-full whitespace-nowrap pr-4 pt-2 pb-2"):
        with ui.element("thead"):
            with ui.element("tr"):
                ui.element("th", "Player ID")
                ui.element("th", "Name")
                ui.element("th", "Rating")
        with ui.element("tbody"):
            for player in player_ratings:
                with ui.element("tr").classes("cursor-pointer hover:bg-base-100") as row_ele:
                    row_ele.attributes["onclick"] = f"window.location.href='{routes['player'].format(player_id=player.player_id)}'"
                    ui.element("td", str(player.player_id))
                    ui.element("td", player.name)
                    with ui.element("td", f"{player.rating_after}"):
                        render_rating_diff(player.rating_after, player.rating_before)


def render_match_list(con: Session):
    matches = list_matches(con, limit=10)

    with ui.element("table").classes("table table-zebra table-auto bg-base-300 overflow-scroll w-full whitespace-nowrap pr-4 pt-2 pb-2"):
        with ui.element("thead"):
            with ui.element("tr"):
                ui.element("th", "id")
                ui.element("th", "Winning team score")
                ui.element("th", "Losing team score")
                ui.element("th", "Created At")
        with ui.element("tbody"):
            for match in matches:
                with ui.element("tr").classes("cursor-pointer hover:bg-base-100") as row_ele:
                    row_ele.attributes["onclick"] = f"window.location.href='{routes['match'].format(match_id=match.id)}'"
                    ui.element("td", str(match.id))
                    ui.element("td", str(match.winning_team_score))
                    ui.element("td", str(match.losing_team_score))
                    ui.element("td", match.created_at.strftime("%Y-%m-%d %H:%M:%S"))

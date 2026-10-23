from database.dto import MatchDetails, PlayerRatingInfo
from database.queries import (
    get_match_details,
    get_player_ratings_after_match,
    list_matches,
)
from pages import routes
from pages.fragment.arrow import render_rating_diff
from sqlalchemy.orm import Session
from uiwiz import ui


def format_team_label(player_1_name: str, player_2_name: str | None) -> str:
    if player_2_name is None:
        return player_1_name
    return f"{player_1_name} & {player_2_name}"


def render_match_from_id(match_id: str, con: Session, *, admin_enabled: bool = False, is_admin: bool = False):
    match_details = get_match_details(con, match_id)
    player_ratings: list[PlayerRatingInfo] = get_player_ratings_after_match(con, match_id)

    render_match(match_details, player_ratings, admin_enabled=admin_enabled, is_admin=is_admin)


def render_match(
    match_details: MatchDetails,
    player_ratings: list[PlayerRatingInfo],
    *,
    admin_enabled: bool = False,
    is_admin: bool = False,
):
    ui.element("h2", "Match Details")
    ui.element("p", f"Match ID: {match_details.matchid}")
    ui.element("p", f"Created At: {match_details.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    ui.element("p", f"Team 1 Score: {match_details.team1_score}")
    ui.element("p", f"Team 2 Score: {match_details.team2_score}")
    if is_admin:
        ui.link("Edit match", routes["match_edit"].format(match_id=match_details.matchid))
        ui.link("Remove match", routes["match_remove"].format(match_id=match_details.matchid))
    elif admin_enabled:
        ui.link("Administrator sign in", "/admin/login")
    with ui.element().classes(ui.table._classes_container):
        with ui.element("table").classes(
            "table table-zebra table-auto bg-base-300 overflow-scroll w-full whitespace-nowrap pr-4 pt-2 pb-2"
        ):
            with ui.element("thead"):
                with ui.element("tr"):
                    ui.element("th", "Name")
                    ui.element("th", "Rating")
            with ui.element("tbody"):
                for player in player_ratings:
                    with ui.element("tr").classes("cursor-pointer hover:bg-base-100") as row_ele:
                        row_ele.attributes["onclick"] = (
                            f"window.location.href='{routes['player_detail'].format(player_id=player.player_id)}'"
                        )
                        ui.element("td", player.name)
                        with ui.element("td", f"{player.rating_after}"):
                            render_rating_diff(player.rating_after, player.rating_before)


def render_match_list(con: Session):
    matches = list_matches(con, limit=10)

    with ui.element().classes(ui.table._classes_container):
        with ui.element("table").classes(
            "table table-zebra table-auto bg-base-300 overflow-scroll w-full whitespace-nowrap pr-4 pt-2 pb-2"
        ):
            with ui.element("thead"):
                with ui.element("tr"):
                    ui.element("th", "Team 1")
                    ui.element("th", "Team 1 score")
                    ui.element("th", "Team 2 score")
                    ui.element("th", "Team 2")
                    ui.element("th", "Created At")
            with ui.element("tbody"):
                for match in matches:
                    with ui.element("tr").classes("cursor-pointer hover:bg-base-100") as row_ele:
                        row_ele.attributes["onclick"] = (
                            f"window.location.href='{routes['match_detail'].format(match_id=match.id)}'"
                        )
                        match_details = get_match_details(con, match.id)

                        ui.element(
                            "td",
                            format_team_label(match_details.player1_name, match_details.player2_name),
                        )
                        ui.element("td", str(match_details.team1_score))
                        ui.element("td", str(match_details.team2_score))
                        ui.element(
                            "td",
                            format_team_label(match_details.player3_name, match_details.player4_name),
                        )
                        ui.element("td", match.created_at.strftime("%Y-%m-%d %H:%M:%S"))

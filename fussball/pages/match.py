from datetime import UTC
from uuid import UUID

from auth import admin_auth_configured, require_admin
from config import Settings
from database.dto import MatchDetails
from database.queries import get_match_details
from database.setup import Connection
from database.tables import Match, Player
from elo.match_correction import InvalidPlayerSelectionError, correct_match_scores
from elo.match_errors import MatchNotFoundError
from elo.match_removal import remove_match
from elo.upload_match import MatchCorrection
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import or_, select
from uiwiz import PageRouter, ui

from pages import routes
from pages.fragment.ui_match import render_match_from_id, render_match_list

match_router = PageRouter()


@match_router.page(routes["match_edit"])
async def edit_match_page(match_id: str, con: Connection, _: None = Depends(require_admin)):
    match = con.get(Match, UUID(match_id))
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    match_details = get_match_details(con, match.id)
    render_edit_match_form(match_details, get_match_player_options(con, match_details))


@match_router.ui(routes["match_edit"])
async def edit_match_score(
    match_id: str,
    data: MatchCorrection,
    con: Connection,
    response: Response,
    _: None = Depends(require_admin),
):
    try:
        changes = correct_match_scores(con, UUID(match_id), data)
    except MatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Match not found") from exc
    except InvalidPlayerSelectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    render_match_from_id(match_id, con, admin_enabled=True, is_admin=True)
    if changes.lineup_changed and changes.played_at_changed:
        ui.toast("Match updated").success()
    elif changes.lineup_changed:
        ui.toast("Match lineup updated").success()
    elif changes.played_at_changed:
        ui.toast("Match played-at time updated").success()
    else:
        ui.toast("Match scores updated").success()
    response.headers["HX-Push-Url"] = routes["match_detail"].format(match_id=match_id)


@match_router.page(routes["match_remove"])
async def confirm_match_removal(match_id: str, con: Connection, _: None = Depends(require_admin)):
    match_uuid = UUID(match_id)
    if con.get(Match, match_uuid) is None:
        raise HTTPException(status_code=404, detail="Match not found")
    render_match_removal_confirmation(get_match_details(con, match_uuid))


@match_router.ui(routes["match_remove"])
async def remove_match_action(
    match_id: str,
    con: Connection,
    response: Response,
    _: None = Depends(require_admin),
):
    try:
        remove_match(con, UUID(match_id))
    except MatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Match not found") from exc

    render_match_list(con)
    ui.toast("Match removed").success()
    response.headers["HX-Push-Url"] = routes["Matches"]


@match_router.page(routes["match_detail"])
async def view_match(match_id: str, con: Connection, request: Request):
    settings: Settings = request.app.state.admin_settings
    enabled = admin_auth_configured(settings)
    is_admin = enabled and bool(request.session.get("admin_authenticated"))
    render_match_from_id(match_id, con, admin_enabled=enabled, is_admin=is_admin)


@match_router.page(routes["Matches"])
def list_matches(con: Connection):
    render_match_list(con)


def render_match_removal_confirmation(match_details: MatchDetails) -> None:
    team_1 = match_details.player1_name + (f" & {match_details.player2_name}" if match_details.player2_name else "")
    team_2 = match_details.player3_name + (f" & {match_details.player4_name}" if match_details.player4_name else "")
    with ui.form().on_submit(routes["match_remove"].format(match_id=match_details.matchid), swap="outerHTML"):
        ui.element("h2", "Permanently remove this match?")
        ui.element("p", f"Match: {team_1} {match_details.team1_score} – {match_details.team2_score} {team_2}")
        ui.element("p", f"Played at: {match_details.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        ui.element("p", "This permanently removes the match and recalculates ratings. This cannot be undone.")
        ui.button("Permanently remove match").classes("btn-danger")
        ui.link("Cancel", routes["match_detail"].format(match_id=match_details.matchid))


def get_match_player_options(con: Connection, match_details: MatchDetails) -> list[tuple[str, str]]:
    current_player_ids = (
        match_details.player1_id,
        match_details.player2_id,
        match_details.player3_id,
        match_details.player4_id,
    )
    players = con.execute(
        select(Player)
        .where(or_(Player.active.is_(True), Player.id.in_(current_player_ids)))
        .order_by(Player.name, Player.id)
    ).scalars()
    return [(str(player.id), player.name) for player in players]


def render_edit_match_form(match_details: MatchDetails, players: list[tuple[str, str]]) -> None:
    with (
        ui.form()
        .on_submit(
            routes["match_edit"].format(match_id=match_details.matchid),
            swap="outerHTML",
        )
        .classes("border border-base-content rounded-lg shadow-lg w-full items-center")
    ):
        ui.element("h2", "Edit match scores, lineup, and played-at time")

        with ui.element().classes("flex flex-col items-center justify-center gap-4 pb-2 w-full"):
            ui.label("Played at (UTC)")
            played_at_input = ui.element("input").classes("input input-bordered w-full max-w-xs")
            played_at_input.attributes["type"] = "datetime-local"
            played_at_input.attributes["name"] = "date"
            played_at = match_details.created_at
            if played_at.tzinfo is not None:
                played_at = played_at.astimezone(UTC).replace(tzinfo=None)
            played_at_input.attributes["value"] = played_at.isoformat(timespec="seconds")
            played_at_input.attributes["step"] = "1"

        with ui.element().classes("flex flex-col gap-2 w-full"):
            ui.element("h3", "Team 1").classes("text-lg font-semibold text-center")
            render_player_dropdown("Team 1 player 1", "player_1", players, match_details.player1_id)
            render_player_dropdown("Team 1 player 2", "player_2", players, match_details.player2_id)
            render_score_input("Team 1 score", "score_team_1", match_details.team1_score)

        with ui.element().classes("flex flex-col gap-2 w-full"):
            ui.element("h3", "Team 2").classes("text-lg font-semibold text-center")
            render_player_dropdown("Team 2 player 1", "player_3", players, match_details.player3_id)
            render_player_dropdown("Team 2 player 2", "player_4", players, match_details.player4_id)
            render_score_input("Team 2 score", "score_team_2", match_details.team2_score)

        with ui.element().classes("flex items-center justify-center w-full"):
            ui.button("Save match").classes("btn-primary")


def render_player_dropdown(
    label: str,
    name: str,
    players: list[tuple[str, str]],
    selected_id: UUID | None,
) -> None:
    with ui.element().classes("flex flex-col items-center justify-center gap-4 pb-2 w-full"):
        ui.label(label)
        with ui.element("select").classes("select select-bordered w-full max-w-xs") as dropdown:
            dropdown.attributes["name"] = name
            empty_option = ui.element("option", "No player selected")
            empty_option.attributes["value"] = ""
            if selected_id is None:
                empty_option.attributes["selected"] = "selected"
            for player_id, player_name in players:
                option = ui.element("option", player_name)
                option.attributes["value"] = player_id
                if selected_id is not None and player_id == str(selected_id):
                    option.attributes["selected"] = "selected"


def render_score_input(label: str, name: str, value: int) -> None:
    with ui.element().classes("flex flex-col items-center justify-center gap-4 pb-2 w-full"):
        ui.label(label)
        ui.number(name=name, value=value, min=0, max=10, step=1).classes("w-full max-w-xs")

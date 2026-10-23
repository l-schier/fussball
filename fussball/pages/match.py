from uuid import UUID

from auth import admin_auth_configured, require_admin
from config import Settings
from database.dto import MatchDetails
from database.queries import get_match_details
from database.setup import Connection
from database.tables import Match, Player
from elo.match_correction import (
    InvalidPlayerSelectionError,
    MatchNotFoundError,
    correct_match_scores,
)
from elo.upload_match import MatchCorrection
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import or_, select
from uiwiz import PageRouter, ui

from pages import routes
from pages.fragment.ui_match import render_match_from_id, render_match_list

match_router = PageRouter()


@match_router.page("/match/{match_id}/edit")
async def edit_match_page(match_id: str, con: Connection, _: None = Depends(require_admin)):
    match = con.get(Match, UUID(match_id))
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    match_details = get_match_details(con, match.id)
    render_edit_match_form(match_details, get_match_player_options(con, match_details))


@match_router.ui("/match/{match_id}/edit")
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


@match_router.page(routes["match_detail"])
async def view_match(match_id: str, con: Connection, request: Request):
    settings: Settings = request.app.state.admin_settings
    enabled = admin_auth_configured(settings)
    is_admin = enabled and bool(request.session.get("admin_authenticated"))
    render_match_from_id(match_id, con, admin_enabled=enabled, is_admin=is_admin)


@match_router.page(routes["Matches"])
def list_matches(con: Connection):
    render_match_list(con)


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
    ui.element("h2", "Edit match scores, lineup, and played-at time")
    with ui.form().on_submit(edit_match_score, swap="outerHTML"):
        ui.label("Played at (UTC)")
        played_at_input = ui.element("input").classes("input input-bordered w-full max-w-xs")
        played_at_input.attributes["type"] = "datetime-local"
        played_at_input.attributes["name"] = "date"
        played_at_input.attributes["value"] = match_details.created_at.replace(tzinfo=None).isoformat()
        played_at_input.attributes["step"] = "any"
        render_player_dropdown("Team 1 player 1", "player_1", players, match_details.player1_id)
        render_player_dropdown("Team 1 player 2", "player_2", players, match_details.player2_id)
        ui.number(
            name="score_team_1",
            value=match_details.team1_score,
            min=0,
            max=10,
            step=1,
        )
        render_player_dropdown("Team 2 player 1", "player_3", players, match_details.player3_id)
        render_player_dropdown("Team 2 player 2", "player_4", players, match_details.player4_id)
        ui.number(
            name="score_team_2",
            value=match_details.team2_score,
            min=0,
            max=10,
            step=1,
        )
        ui.button("Save match")


def render_player_dropdown(
    label: str,
    name: str,
    players: list[tuple[str, str]],
    selected_id: UUID | None,
) -> None:
    with ui.element().classes("flex flex-col items-center gap-2 w-full"):
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

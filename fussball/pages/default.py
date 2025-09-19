from datetime import datetime
from uiwiz import ui, PageRouter
from fussball.database.setup import Connection
from sqlalchemy import text
from fussball.elo.upload_match import UploadMatch, UploadMatchOptional
from sqlalchemy import select

from fussball.database.tables import Player
from fussball.elo.elo_calculator import process_game_data

default_route = PageRouter()

def normlize_input(match_result: UploadMatchOptional) -> UploadMatch:
    if match_result.player_1 is None or match_result.player_2 is None:
        if match_result.player_1 is None and match_result.player_2 is not None:
            match_result.player_1 = match_result.player_2
            match_result.player_2 = None
        elif match_result.player_3 is None and match_result.player_4 is not None:
            match_result.player_3 = match_result.player_4
            match_result.player_4 = None
    return UploadMatch.model_validate(match_result.model_dump())


async def get_players(con: Connection):
    players = (await con.execute(select(Player).filter(Player.active))).scalars().all()
    return [ui.dropdownItem(name=row.name, value=row.id) for row in players]

def form_setup(player_options: list[ui.dropdownItem]):
    with ui.form().on_submit(submit_match, swap="outerHTML")\
        .classes("border border-base-content rounded-lg shadow-lg w-full items-center") as form:
        form.attributes["autocomplete"] = "off"
        ui.element("h2", "Upload Match")

        draw_player_dropdown("Player 1", player_options)
        draw_player_dropdown("Player 2", player_options)
        draw_score_input("Score Team 1")

        draw_player_dropdown("Player 3", player_options)
        draw_player_dropdown("Player 4", player_options)
        draw_score_input("Score Team 2")

        with ui.element().classes("flex items-center justify-center w-full"):
            ui.label("Match Date")
        with ui.element().classes("flex items-center justify-center w-full"):
            ui.datepicker(name="date", value=datetime.now()).classes("input")
        with ui.element().classes("flex items-center justify-center w-full"):
            ui.button("Submit game").classes("btn-primary")


@default_route.ui("/match/submit")
async def submit_match(data: UploadMatchOptional, con: Connection):
    print(data)
    data = normlize_input(data)
    player_options = await get_players(con)
    form_setup(player_options)
    ui.toast("Match submitted!").success()
    await process_game_data(data, con)

@default_route.page("/")
async def default_page(con: Connection):
    ui.element("h1", "Welcome to the Fussball App")
    res = await con.execute(text("SELECT 1+1 AS result"))
    ui.element("p", "Dynamic value from DB:")
    ui.element("pre", f"1 + 1 = {res.scalar_one()}")

    player_options = await get_players(con)
    form_setup(player_options)

def draw_player_dropdown(player_name: str, options: list[ui.dropdownItem]):
    with ui.element().classes("flex items-center justify-center gap-4 pb-2 w-full"):
        with ui.element().classes("flex flex-col items-center gap-4 w-full"):        
            ui.label(player_name)
            ui.dropdown(
                name=player_name.lower().replace(" ", "_"),
                items=options,
                placeholder="Select player",
            )

def draw_score_input(score_name: str):
    with ui.element().classes("flex items-center justify-center gap-4 pb-2 w-full"):
        ui.number(name=score_name.lower().replace(" ", "_"), value=None, min=0, max=10, step=1, placeholder="0-10").classes("w-1/4")

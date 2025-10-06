from uuid import uuid4
from pydantic import BaseModel
from uiwiz import Page, PageDefinition, PageRouter
from fussball.database.setup import Connection
from fussball.database.queries_players import list_players, show_player
from fussball.pages.fragment.ui_player import render_player, render_player_list
from fussball.database.tables import Player
from uiwiz import ui
from sqlalchemy import text

from fussball.pages.layout import Layout

player_router = PageRouter(prefix="/player")

# custom width for player details
class PageContentWidth(Layout):
    def __init__(self) -> None:
        super().__init__()
        self.max_width = "max-w-7xl"


class PlayerDTO(BaseModel):
    name: str


@player_router.ui("/submit/new")
def submit_player(data: PlayerDTO, con: Connection):
    result = con.execute(text("SELECT name FROM player WHERE name = :name"), {"name": data.name})
    if result.first():
        ui.toast(f"Player with name {data.name} already exists").error()
        return
    new_player = Player(id=uuid4(), name=data.name, active=True)
    con.add(new_player)
    con.commit()

    ui.toast(f"Creating player {data.name}").success()


@player_router.page("/new")
def new_player(con: Connection):
    with ui.form().classes("border border-base-content rounded-lg shadow-lg w-full items-center").on_submit(submit_player, swap="none"):
        ui.label("Add new player")
        ui.input(name="name", placeholder="Player Name").set_floating_label().classes("input")
        ui.button("Create Player").classes("btn-primary")


@player_router.page("/{player_id}", page_definition_class=PageContentWidth, title="Player Details")
def view_player(player_id: str, con: Connection, page: Page):
    player = show_player(con, player_id)
    render_player(player)

@player_router.page("/")
def player_list_page(con: Connection):
    players = list_players(con)
    render_player_list(players)

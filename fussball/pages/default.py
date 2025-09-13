from collections import namedtuple
from datetime import datetime
from typing import Optional
from uiwiz import ui, PageRouter
from fussball.database.setup import Connection
from sqlalchemy import text
from pydantic import BaseModel, Field
from sqlalchemy import select

from fussball.database.tables import Player

default_route = PageRouter()

Options = namedtuple("Options", ["label", "value"])

class UploadMatch(BaseModel):
    player_1: str
    player_2: str
    score_team_1: int = Field(ge=0, lt=11)
    
    player_3: str
    player_4: str
    score_team_2: int = Field(ge=0, lt=11)

    date: datetime



def get_players(con: Connection):
    players = con.scalars(select(Player).filter(Player.active)).all()
    return [Options(label=row.name, value=row.id) for row in players]


@default_route.post("/match/submit")
async def submit_match(data: UploadMatch):
    print(data)
    pass

@default_route.page("/")
async def default_page(con: Connection):
    ui.element("h1", "Welcome to the Fussball App")
    res = con.execute(text("SELECT 1+1 AS result"))
    ui.element("p", "Dynamic value from DB:")
    ui.element("pre", res.fetchall())

    player_options = get_players(con)
    with ui.form().classes("border border-base-content rounded-lg shadow-lg w-full items-center") as form:
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
        ui.button("Submit game").on_click(submit_match, swap="none").classes("btn-primary")



def draw_player_dropdown(player_name: str, options: list[Options]):
    with ui.element().classes("flex items-center justify-center gap-4 pb-2 w-full"):
        with ui.element().classes("flex flex-col items-center gap-4 w-full"):        
            ui.label(player_name)
            Dropdown(
                name=player_name.lower().replace(" ", "_"),
                items=options,
                placeholder="Select player",
            )

def draw_score_input(score_name: str):
    with ui.element().classes("flex items-center justify-center gap-4 pb-2 w-full"):
        i = ui.input(name=score_name.lower().replace(" ", "_"), placeholder="0-10").classes("w-1/4")
        i.attributes["type"] = "number"
        i.attributes["min"] = "0"
        i.attributes["max"] = "10"


    
class Dropdown(ui.element):
    root_class: str = "select "
    root_size: str = "select-{size}"
    _classes: str = "select-bordered w-full max-w-xs"

    def __init__(self, name: str, items: list[Options], placeholder: Optional[str] = None) -> None:
        super().__init__("select")
        self.attributes["name"] = name
        self.classes()
        self.size(self._size)
        with self:
            if placeholder and placeholder not in [item.label for item in items]:
                ui.element("option disabled selected", content=placeholder)
            for v in items:
                e = ui.element("option", content=v.label)
                e.value = v.value
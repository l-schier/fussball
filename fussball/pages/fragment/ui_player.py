from sqlalchemy.orm import Session
from uiwiz import ui

def render_player(player_id: str, con: Session):
    pass

def render_player_list(players: list):
    with ui.element("table").classes("table table-zebra table-auto bg-base-300 overflow-scroll w-full whitespace-nowrap pr-4 pt-2 pb-2"):
        with ui.element("thead"):
            with ui.element("tr"):
                ui.element("th", "Player ID")
                ui.element("th", "Name")
                ui.element("th", "Ranking")
        with ui.element("tbody"):
            for player in players:
                with ui.element("tr"):
                    ui.element("td", str(player.id))
                    ui.element("td", player.name)
                    ui.element("td", str(player.ranking))
    
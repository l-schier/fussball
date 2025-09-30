from sqlalchemy.orm import Session
from uiwiz import ui
from fussball.database.dto import PlayerWithRating

def render_player(player: PlayerWithRating):
    ui.element("h2", player.name)
    ui.element("p", f"Ranking: {player.ranking}")


    ui.element("h3", "Last 10 Ratings")
    with ui.element("table").classes("table table-zebra table-auto bg-base-300 overflow-scroll w-full whitespace-nowrap pr-4 pt-2 pb-2"):
        with ui.element("thead"):
            with ui.element("tr"):
                ui.element("th", "Created At")
                ui.element("th", "Rating")
        with ui.element("tbody"):
            for rating in player.history:
                with ui.element("tr"):
                    ui.element("td", str(rating['rating']))
                    ui.element("td", str(rating['created_at'].strftime('%Y-%m-%d %H:%M:%S')))

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
    
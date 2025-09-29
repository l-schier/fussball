from uiwiz import ui, PageRouter
from sqlalchemy.orm import Session
from fussball.database.setup import Connection
from fussball.database.queries_players import list_players
from fussball.pages.fragment.ui_player import render_player, render_player_list

player_router = PageRouter(prefix="/player")

@player_router.page("/{player_id}")
def view_player(player_id: str):
    pass

@player_router.page("/")
def player_list_page(con: Connection):
    players = list_players(con)
    render_player_list(players)

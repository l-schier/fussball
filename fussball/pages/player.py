from uiwiz import ui, PageRouter
from sqlalchemy.orm import Session
from fussball.pages.fragment.ui_player import render_player, render_player_list

player_router = PageRouter(prefix="/player")

@player_router.page("/{player_id}")
def view_player(player_id: str):
    pass

@player_router.page("/")
def list_players(con: Session):
    pass
    
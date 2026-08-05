from uuid import uuid4
import uuid
import math
from pydantic import BaseModel
from uiwiz import Page, PageRouter
from database.setup import Connection
from database.queries_players import (
    count_player_ratings,
    get_player_matches,
    get_player_ratings_page,
    list_players,
    show_player,
)
from pages.fragment.ui_player import render_player, render_player_list, render_player_ratings_table_content
from database.tables import Player
from datetime import datetime, timezone
from uiwiz import ui
from sqlalchemy import text

from pages.layout import Layout

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
    new_player = Player(
        id=uuid4(),
        name=data.name,
        active=True,
        created_at=datetime.now(tz=timezone.utc),
    )
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
    player_uuid = uuid.UUID(player_id)
    player = show_player(con, player_uuid)
    player_match_count = get_player_matches(con, player_uuid)
    total_ratings = count_player_ratings(con, player_uuid)
    total_pages = max(1, math.ceil(total_ratings / 10))
    ratings = get_player_ratings_page(con, player_uuid, page=1, page_size=10)

    render_player(player, player_match_count, player_uuid, ratings, total_pages, player_ratings_page)


@player_router.ui("/{player_id}/ratings/{page}")
def player_ratings_page(player_id: str, page: int, con: Connection):
    player_uuid = uuid.UUID(player_id)
    safe_page = max(page, 1)
    total_ratings = count_player_ratings(con, player_uuid)
    total_pages = max(1, math.ceil(total_ratings / 10))
    safe_page = min(safe_page, total_pages)
    ratings = get_player_ratings_page(con, player_uuid, page=safe_page, page_size=10)

    render_player_ratings_table_content(
        player_id=player_uuid,
        ratings=ratings,
        page=safe_page,
        total_pages=total_pages,
        on_page_change=player_ratings_page,
    )


@player_router.page("/")
def player_list_page(con: Connection):
    players = list_players(con)
    render_player_list(players)

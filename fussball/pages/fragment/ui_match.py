from typing import Callable, List
from uiwiz import ui
from fussball.database.dto import MatchDetails, PlayerRatingInfo
from fussball.database.tables import Match
from sqlalchemy.orm import Session

from fussball.database.queries import get_match_details, get_player_ratings_after_match, list_matches
from fussball.pages.fragment.arrow import render_rating_diff

def render_match_from_id(match_id: str, con: Session):
    match_details = get_match_details(con, match_id)
    player_ratings: list[PlayerRatingInfo] = get_player_ratings_after_match(con, match_id)
    
    render_match(match_details, player_ratings)

def render_match(match_details: MatchDetails, player_ratings: list[PlayerRatingInfo]):
    ui.element("h2", "Match Details")
    ui.element("p", f"Match ID: {match_details.matchid}")
    ui.element("p", f"Created At: {match_details.created_at}")
    ui.element("p", f"Team 1 Score: {match_details.team1_score}")
    ui.element("p", f"Team 2 Score: {match_details.team2_score}")

    with ui.element("table").classes("table table-zebra table-auto bg-base-300 overflow-scroll w-full whitespace-nowrap pr-4 pt-2 pb-2"):
        with ui.element("thead"):
            with ui.element("tr"):
                ui.element("th", "Player ID")
                ui.element("th", "Name")
                ui.element("th", "Rating")
        with ui.element("tbody"):
            for player in player_ratings:
                with ui.element("tr"):
                    ui.element("td", str(player.player_id))
                    ui.element("td", player.name)
                    with ui.element("td", f"{player.rating_after}"):
                        render_rating_diff(player.rating_after, player.rating_before)


class MatchListTable(ui.element):
    def __init__(self, data: List[Match], redirect: Callable) -> None:
        container = ui.element("div").classes("w-full")
        with container:
            super().__init__()
        self.classes(ui.table._classes_container)

        self.schema = []
        if data:
            self.schema = ["id", "winning_team_score", "losing_team_score", "created_at"]

        self.container = container
        self.data = data
        self.did_render: bool = False
        self.redirect = redirect
    
    def before_render(self) -> None:
        super().before_render()
        if self.did_render:
            return None

        with self:
            with ui.element("table").classes(ui.table._classes_table):
                # columns
                with ui.element("thead"):
                    with ui.element("tr"):
                        for col in self.schema:
                            ui.element("th", content=col)
                # rows
                with ui.element("tbody"):
                    for row in self.data:
                        self.render_row(row)
        
        self.did_render = True

    def render_row(self, row: Match):
        with ui.element("tr").classes("cursor-pointer hover:bg-base-100") as row_ele:
            row_ele.event = {
                "func": self.redirect,
                "trigger": "click",
                "target": "this",
                "swap": "innerHTML",
                "params": {"match_id": row.id},
            }
            for col in self.schema:
                ui.element("td", content=str(getattr(row, col, "")))

def render_match_list(con: Session, redirect: Callable):
    matches = list_matches(con, limit=10)
    MatchListTable(matches, redirect=redirect)

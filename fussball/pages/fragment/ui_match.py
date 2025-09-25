from typing import Callable, List, Optional
from uiwiz import ui
from app import rating
from fussball.database.dto import MatchDetails, PlayerRatingInfo
from fussball.database.tables import Match
from sqlalchemy.orm import Session

from fussball.database.queries import get_match_details, get_player_ratings_after_match, list_matches

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

    with ui.element("table").classes("table w-full"):
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
                    rating_diff = player.rating_after - player.rating_before if player.rating_before is not None and player.rating_after is not None else 0
                    arrow = "↑" if rating_diff > 0 else ("↓" if rating_diff < 0 else "")
                    with ui.element("td", f"{player.rating_after}"):
                        cls = "text-green-500" if rating_diff > 0 else "text-red-500"
                        ui.element("span", f" {arrow}").classes(cls)
                        ui.element("span", f" ({rating_diff:+})").classes(cls)


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

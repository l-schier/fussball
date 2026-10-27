from database.queries_teams import TeamRanking, list_team_rankings
from database.setup import Connection
from uiwiz import PageRouter, ui

team_router = PageRouter(prefix="/team")


@team_router.page("/")
def team_rankings_page(con: Connection) -> None:
    rankings = list_team_rankings(con)
    ui.element("h1", "Team Rankings").classes("text-2xl font-bold")

    if not rankings:
        ui.element("p", "No teams have been recorded yet.")
        return

    render_team_rankings(rankings)


def render_team_rankings(rankings: list[TeamRanking]) -> None:
    with (
        ui.element("div").classes("overflow-x-auto"),
        ui.element("table").classes("table table-zebra table-auto bg-base-300 w-full"),
    ):
        with ui.element("thead"), ui.element("tr"):
            ui.element("th", "Rank")
            ui.element("th", "Team")
            ui.element("th", "Rating")
        with ui.element("tbody"):
            for team in rankings:
                with ui.element("tr"):
                    ui.element("td", str(team.rank) if team.rank is not None else "Unranked")
                    ui.element("td", " & ".join(team.members))
                    ui.element("td", str(team.rating) if team.rating is not None else "—")

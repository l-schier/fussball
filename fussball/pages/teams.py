import math
from uuid import UUID

from database.queries_teams import (
    TeamDetails,
    TeamMatchHistory,
    TeamRanking,
    TeamWinStats,
    count_team_matches,
    get_team_details,
    get_team_match_history_page,
    get_team_win_stats,
    list_team_rankings,
)
from database.setup import Connection
from fastapi import HTTPException
from uiwiz import PageRouter, ui

from pages import routes
from pages.page_layout import PageContentWidth

TEAM_MATCH_PAGE_SIZE = 10
team_router = PageRouter(prefix="/team")


@team_router.page("/")
def team_rankings_page(con: Connection) -> None:
    rankings = list_team_rankings(con)
    ui.element("h1", "Team Rankings").classes("text-2xl font-bold")

    if not rankings:
        ui.element("p", "No teams have been recorded yet.")
        return

    render_team_rankings(rankings)


@team_router.page("/{team_id}", page_definition_class=PageContentWidth, title="Team Details")
def team_details_page(team_id: str, con: Connection) -> None:
    team_uuid = _parse_team_id(team_id)
    team = get_team_details(con, team_uuid)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")

    win_stats = get_team_win_stats(con, team_uuid)
    total_pages = max(1, math.ceil(win_stats.matches_played / TEAM_MATCH_PAGE_SIZE))
    matches = get_team_match_history_page(con, team_uuid, page=1, page_size=TEAM_MATCH_PAGE_SIZE)
    render_team_details(team, win_stats, matches, page=1, total_pages=total_pages)


@team_router.ui(routes["team_match_history"].removeprefix(team_router.prefix))
def team_match_history_page(team_id: str, page: int, con: Connection) -> None:
    team_uuid = _parse_team_id(team_id)
    if get_team_details(con, team_uuid) is None:
        raise HTTPException(status_code=404, detail="Team not found")

    total_matches = count_team_matches(con, team_uuid)
    total_pages = max(1, math.ceil(total_matches / TEAM_MATCH_PAGE_SIZE))
    safe_page = min(max(page, 1), total_pages)
    matches = get_team_match_history_page(con, team_uuid, page=safe_page, page_size=TEAM_MATCH_PAGE_SIZE)
    render_team_match_history_content(team_uuid, matches, page=safe_page, total_pages=total_pages)


def _parse_team_id(team_id: str) -> UUID:
    try:
        return UUID(team_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Team not found") from exc


def render_team_details(
    team: TeamDetails,
    win_stats: TeamWinStats,
    matches: list[TeamMatchHistory],
    page: int,
    total_pages: int,
) -> None:
    ui.element("h1", " & ".join(team.members)).classes("text-2xl font-bold")
    current_rating = matches[0].rating if matches else None
    if current_rating is None:
        ui.element("p", "Current rating: Unranked")
    else:
        ui.element("p", f"Current rating: {current_rating:.0f}")
    ui.element("h3", f"Total Matches: {win_stats.matches_played}")
    if win_stats.matches_played:
        win_rate = win_stats.wins / win_stats.matches_played * 100
        win_label = "win" if win_stats.wins == 1 else "wins"
        match_label = "match" if win_stats.matches_played == 1 else "matches"
        ui.element(
            "h3",
            f"Lifetime Win Rate: {win_stats.wins} {win_label} / {win_stats.matches_played} {match_label} ({win_rate:.1f}%)",
        )
    else:
        ui.element("h3", "No matches yet")

    with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2"):
        with ui.element():
            ui.element("h2", "Recent matches").classes("text-xl font-semibold")
            render_team_match_history(team.team_id, matches, page, total_pages)
        render_team_rating_chart(matches)


def render_team_rating_chart(matches: list[TeamMatchHistory]) -> None:
    rating_history = [match for match in reversed(matches) if match.rating is not None]
    ratings = [match.rating for match in rating_history]
    min_rating = ((min(ratings) // 100) * 100 - 100) if ratings else 0
    max_rating = ((max(ratings) // 100) * 100 + 100) if ratings else 100

    with ui.element() as chart:
        chart.attributes["id"] = "team-rating-history-chart"
        ui.echart(
            {
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "line"}},
                "xAxis": {
                    "type": "category",
                    "data": [match.played_at.strftime("%Y-%m-%d") for match in rating_history],
                },
                "yAxis": {"type": "value", "min": min_rating, "max": max_rating},
                "series": [
                    {
                        "data": ratings,
                        "type": "line",
                        "smooth": True,
                    }
                ],
            }
        )


def render_team_match_history(
    team_id: UUID,
    matches: list[TeamMatchHistory],
    page: int,
    total_pages: int,
) -> None:
    with ui.element() as container:
        container.attributes["id"] = "team-match-history"
        render_team_match_history_content(team_id, matches, page, total_pages)


def render_team_match_history_content(
    team_id: UUID,
    matches: list[TeamMatchHistory],
    page: int,
    total_pages: int,
) -> None:
    if not matches:
        ui.element("p", "No matches have been recorded for this team yet.")
        return

    with (
        ui.element("div").classes("overflow-x-auto"),
        ui.element("table").classes("table table-zebra table-auto bg-base-300 w-full"),
    ):
        with ui.element("thead"), ui.element("tr"):
            ui.element("th", "Played at")
            ui.element("th", "Opponent")
            ui.element("th", "Score")
            ui.element("th", "Result")
            ui.element("th", "Rating")
        with ui.element("tbody"):
            for match in matches:
                with ui.element("tr"):
                    with ui.element("td"):
                        ui.link(
                            match.played_at.strftime("%Y-%m-%d %H:%M:%S"),
                            routes["match_detail"].format(match_id=match.match_id),
                        )
                    ui.element("td", " & ".join(match.opponent_members))
                    ui.element("td", f"{match.team_score}–{match.opponent_score}")
                    ui.element("td", "Win" if match.won else "Loss")
                    ui.element("td", f"{match.rating:.0f}" if match.rating is not None else "—")

    with ui.element("div").classes("mt-3 flex items-center justify-between"):
        previous_button = ui.button("Prev").classes("btn btn-sm")
        previous_button.on_click(
            routes["team_match_history"].format(team_id=team_id, page=max(page - 1, 1)),
            target="team-match-history",
            swap="innerHTML",
        )
        if page <= 1:
            previous_button.attributes["disabled"] = True  # ty: ignore[invalid-assignment]

        ui.element("span", f"Page {page} of {total_pages}").classes("text-sm")

        next_button = ui.button("Next").classes("btn btn-sm")
        next_button.on_click(
            routes["team_match_history"].format(team_id=team_id, page=min(page + 1, total_pages)),
            target="team-match-history",
            swap="innerHTML",
        )
        if page >= total_pages:
            next_button.attributes["disabled"] = True  # ty: ignore[invalid-assignment]


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
                with ui.element("tr").classes("cursor-pointer hover:bg-base-100") as row:
                    row.attributes["onclick"] = (
                        f"window.location.href='{routes['team_detail'].format(team_id=team.team_id)}'"
                    )
                    ui.element("td", str(team.rank) if team.rank is not None else "Unranked")
                    with ui.element("td"):
                        ui.link(" & ".join(team.members), routes["team_detail"].format(team_id=team.team_id))
                    ui.element("td", f"{team.rating:.0f}" if team.rating is not None else "—")

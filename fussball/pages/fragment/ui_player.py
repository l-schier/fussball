from uuid import UUID
from typing import Callable

from uiwiz import ui
from database.dto import PlayerWithRating
from pages.fragment.arrow import render_rating_diff
from pages import routes


def render_player_ratings_table_content(
    player_id: UUID,
    ratings: list[dict],
    page: int,
    total_pages: int,
    on_page_change: Callable,
    page_size: int = 10,
):
    visible_ratings = ratings[:page_size]

    with ui.element("table").classes(
        "table table-zebra table-auto bg-base-300 overflow-scroll w-full whitespace-nowrap pr-4 pt-2 pb-2"
    ):
        with ui.element("thead"):
            with ui.element("tr"):
                ui.element("th", "Rating")
                ui.element("th", "Created At")
        with ui.element("tbody"):
            for i, rating in enumerate(visible_ratings):
                with ui.element("tr").classes("cursor-pointer hover:bg-base-100") as row_ele:
                    match_id = rating.get("match_id")
                    if match_id:
                        row_ele.attributes["onclick"] = f"window.location.href='{routes['match_detail'].format(match_id=match_id)}'"

                    previous_rating = None
                    if i + 1 < len(visible_ratings):
                        previous_rating = visible_ratings[i + 1]["rating"]
                    elif len(ratings) > page_size:
                        previous_rating = ratings[page_size]["rating"]

                    with ui.element("td", str(rating["rating"])):
                        render_rating_diff(rating["rating"], previous_rating)

                    if created_at := rating.get("created_at"):
                        ui.element("td", str(created_at.strftime("%Y-%m-%d %H:%M:%S")))

    with ui.element("div").classes("mt-3 flex items-center justify-between"):
        prev_button = ui.button("Prev").classes("btn btn-sm")
        prev_button.on_click(
            on_page_change,
            target="ratings-container",
            swap="innerHTML",
            params={"player_id": str(player_id), "page": max(page - 1, 1)},
        )
        if page <= 1:
            prev_button.attributes["disabled"] = True

        ui.element("span", f"Page {page} of {total_pages}").classes("text-sm")

        next_button = ui.button("Next").classes("btn btn-sm")
        next_button.on_click(
            on_page_change,
            target="ratings-container",
            swap="innerHTML",
            params={"player_id": str(player_id), "page": min(page + 1, total_pages)},
        )
        if page >= total_pages:
            next_button.attributes["disabled"] = True


def render_player_ratings_table(
    player_id: UUID,
    ratings: list[dict],
    page: int,
    total_pages: int,
    on_page_change: Callable,
):
    with ui.element() as ratings_container:
        ratings_container.attributes["id"] = "ratings-container"
        render_player_ratings_table_content(player_id, ratings, page, total_pages, on_page_change)


def render_player(
    player: PlayerWithRating,
    player_match_count: int,
    player_id: UUID,
    ratings: list[dict],
    total_pages: int,
    on_page_change: Callable,
):
    ui.element("h2", player.name)
    ui.element("p", f"Ranking: {player.ranking}")
    ui.element("h3", f"Total Matches: {player_match_count}")

    with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2"):
        with ui.element():
            ui.element("h3", "Ratings")
            render_player_ratings_table(player_id, ratings, page=1, total_pages=total_pages, on_page_change=on_page_change)

            ratings = [entry["rating"] for entry in reversed(player.history)] if player.history else []
            min_rating = ((min(ratings) // 100) * 100 - 100) if ratings else 0
            max_rating = ((max(ratings) // 100) * 100 + 100) if ratings else 100

        ui.echart(
            {
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "line"}},
                "xAxis": {
                    "type": "category",
                    "data": ([entry["created_at"].strftime("%Y-%m-%d") for entry in reversed(player.history)] if player.history else []),
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


def render_player_list(players: list[PlayerWithRating]):
    with ui.element().classes(ui.table._classes_container):
        with ui.element("table").classes(
            "table table-zebra table-auto bg-base-300 overflow-scroll w-full whitespace-nowrap pr-4 pt-2 pb-2"
        ):
            with ui.element("thead"):
                with ui.element("tr"):
                    ui.element("th", "Ranking")
                    ui.element("th", "Name")
            with ui.element("tbody"):
                for player in players:
                    with ui.element("tr").classes("cursor-pointer hover:bg-base-100") as row:
                        row.attributes["onclick"] = f"window.location.href='{routes['player_detail'].format(player_id=player.id)}'"
                        ui.element("td", str(player.ranking))
                        ui.element("td", player.name)

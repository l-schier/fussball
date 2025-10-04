from uiwiz import ui
from fussball.database.dto import PlayerWithRating
from fussball.pages.fragment.arrow import render_rating_diff
from fussball.pages.routes import routes


def render_player(player: PlayerWithRating):
    ui.element("h2", player.name)
    ui.element("p", f"Ranking: {player.ranking}")

    ui.element("h3", "Last 10 Ratings")
    with ui.element("table").classes("table table-zebra table-auto bg-base-300 overflow-scroll w-full whitespace-nowrap pr-4 pt-2 pb-2"):
        with ui.element("thead"):
            with ui.element("tr"):
                ui.element("th", "Rating")
                ui.element("th", "Created At")
        with ui.element("tbody"):
            history = player.history
            for i, rating in enumerate(history):
                with ui.element("tr").classes("cursor-pointer hover:bg-base-100") as row_ele:
                    row_ele.attributes["onclick"] = f"window.location.href='{routes['match'].format(match_id=rating.get('match_id'))}'"
                    previous_rating = history[i + 1]["rating"] if i + 1 < len(history) else None
                    with ui.element("td", str(rating["rating"])):
                        render_rating_diff(rating["rating"], previous_rating)

                    if created_at := rating.get("created_at"):
                        ui.element("td", str(created_at.strftime("%Y-%m-%d %H:%M:%S")))
    

    ratings = [entry["rating"] for entry in reversed(player.history)] if player.history else []
    min_rating = ((min(ratings) // 100) * 100 - 100) if ratings else 0
    max_rating = ((max(ratings) // 100) * 100 + 100) if ratings else 100

    ui.echart(
        {
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "line"}},
            "xAxis": {
                "type": "category",
                "data": [entry["created_at"].strftime("%Y-%m-%d") for entry in reversed(player.history)] if player.history else [],
            },
            "yAxis": {"type": "value", "min": min_rating, "max": max_rating},
            "series": [
                {
                    "data": ratings,
                    "type": "line",
                    # "smooth": True,
                }
            ],
        }
    )


def render_player_list(players: list[PlayerWithRating]):
    with ui.element("table").classes("table table-zebra table-auto bg-base-300 overflow-scroll w-full whitespace-nowrap pr-4 pt-2 pb-2"):
        with ui.element("thead"):
            with ui.element("tr"):
                ui.element("th", "Name")
                ui.element("th", "Player ID")
                ui.element("th", "Ranking")
        with ui.element("tbody"):
            for player in players:
                with ui.element("tr").classes("cursor-pointer hover:bg-base-100") as row:
                    row.attributes["onclick"] = f"window.location.href='{routes['player'].format(player_id=player.id)}'"
                    ui.element("td", player.name)
                    ui.element("td", str(player.id))
                    ui.element("td", str(player.ranking))

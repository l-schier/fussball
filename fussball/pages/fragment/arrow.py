from uiwiz import ui


def render_rating_diff(player_rating_after: int, player_rating_before: int | None) -> None:
    rating_diff = player_rating_after - player_rating_before if player_rating_before is not None else 0
    arrow = "↑" if rating_diff > 0 else ("↓" if rating_diff < 0 else "")

    cls = "text-green-500" if rating_diff > 0 else "text-red-500"
    if rating_diff == 0:
        cls = "text-gray-500"
    ui.element("span", f" {arrow}").classes(cls)
    ui.element("span", f" ({rating_diff:+})").classes(cls)

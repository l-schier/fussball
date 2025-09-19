from uiwiz import ui
from fussball.database.dto import PlayerRatingInfo


def render_player_ratings(player_ratings: list[PlayerRatingInfo]):
    ui.table(player_ratings)
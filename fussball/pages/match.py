from uiwiz import PageRouter

from fussball.database.setup import Connection
from fussball.pages.fragment.ui_match import render_match_from_id, render_match_list
from fussball.pages import routes

match_router = PageRouter()

@match_router.page(routes["match_detail"])
async def view_match(match_id: str, con: Connection):
    render_match_from_id(match_id, con)


@match_router.page(routes["match"])
def list_matches(con: Connection):
    render_match_list(con)
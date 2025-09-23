from uiwiz import PageRouter

from fussball.database.setup import Connection
from fussball.pages.fragment.ui_match import render_match_from_id

match_router = PageRouter(prefix="/match")


@match_router.page("/{match_id}")
async def view_match(match_id: str, con: Connection):
    render_match_from_id(match_id, con)
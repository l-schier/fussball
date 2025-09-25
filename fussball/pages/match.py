from fastapi import Response
from uiwiz import PageRouter

from fussball.database.setup import Connection
from fussball.pages.fragment.ui_match import render_match_from_id, render_match_list

match_router = PageRouter(prefix="/match")


@match_router.page("/{match_id}")
async def view_match(match_id: str, con: Connection):
    render_match_from_id(match_id, con)


@match_router.ui("/redirect/{match_id}")
def redirect_to_match(match_id: str, response: Response):
    response.headers["Hx-Redirect"] = f"/match/{match_id}"
    response.status_code = 200

@match_router.page("/")
def list_matches(con: Connection):
    render_match_list(con, redirect=redirect_to_match)
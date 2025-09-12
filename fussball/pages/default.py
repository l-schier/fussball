from uiwiz import ui, PageRouter
from fussball.database.setup import Connection
from sqlalchemy import text
default_route = PageRouter()

@default_route.page("/")
async def default_page(con: Connection):
    ui.element("h1", "Welcome to the Fussball App")
    res = con.execute(text("SELECT 1+1 AS result"))
    ui.element("p", "Dynamic value from DB:")
    ui.element("pre", res.fetchall())

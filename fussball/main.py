from fastapi import Request
from fastapi.responses import HTMLResponse
from uiwiz import UiwizApp, ui
from uiwiz.frame import Frame
import logging
import uvicorn
from fussball.pages.default import default_route
from fussball.pages.layout import Layout, pages
from fussball.database.setup import _tempdir
from fussball.app import FussballApp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def lifespan(app: FussballApp):
    logger.info("Starting up...")
    with _tempdir:
        # Keep the temporary directory alive for the app lifetime
        yield
    logger.info("Shutting down...")

app = UiwizApp(lifespan=lifespan, title="Fussball App", page_definition_class=Layout, theme="dark")

app.include_router(default_route)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

async def not_found():
    with ui.container(padding="p-4"):
        ui.markdown("Page not found. Please check the URL or return to the home page.")
        for page in pages:
            ui.link(page, page)

@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: Exception):
    await app.page_definition_class().render(not_found, request, title="Not Found")
    return HTMLResponse(
        content=Frame.get_stack().render(),
        status_code=404,
        media_type="text/html",
    )

if __name__ == "__main__":
    uvicorn.run("fussball.main:app", host="0.0.0.0", port=8000, reload=True)
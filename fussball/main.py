import logging

import uvicorn
from auth import admin_auth_configured
from config import Settings, settings
from fastapi import Request
from fastapi.responses import HTMLResponse
from pages.admin import admin_router
from pages.default import default_route
from pages.layout import Layout, page_routes
from pages.match import match_router as match_route
from pages.player import player_router
from pages.teams import team_router
from starlette.middleware.sessions import SessionMiddleware
from uiwiz import UiwizApp, ui
from uiwiz.frame import Frame

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def lifespan(app: UiwizApp):
    logger.info("Starting up...")
    yield
    logger.info("Shutting down...")


def create_app(app_settings: Settings = settings) -> UiwizApp:
    app = UiwizApp(
        lifespan=lifespan,
        title="Fussball Leaderboard",
        page_definition_class=Layout,  # ty: ignore[invalid-argument-type]
        theme="dark",
    )
    app.state.admin_settings = app_settings
    if admin_auth_configured(app_settings):
        app.add_middleware(
            SessionMiddleware,
            secret_key=app_settings.admin_session_secret,
            session_cookie="fussball_admin",
            same_site="lax",
            https_only=app_settings.admin_session_cookie_secure,
        )

    app.include_router(default_route)
    app.include_router(match_route)
    app.include_router(player_router)
    app.include_router(team_router)
    app.include_router(admin_router)

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    async def not_found():
        with ui.container(padding="p-4"):
            ui.markdown("Page not found. Please check the URL or return to the home page.")
            for page, route in page_routes.items():
                ui.link(page, route)

    @app.exception_handler(404)
    async def not_found_exception_handler(request: Request, exc: Exception):
        await app.page_definition_class().render(not_found, request, title="Not Found")  # ty: ignore[call-non-callable]
        return HTMLResponse(
            content=Frame.get_stack().render(),
            status_code=404,
            media_type="text/html",
        )

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, workers=1)

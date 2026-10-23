from hmac import compare_digest

from auth import admin_auth_configured
from fastapi import HTTPException, Request, Response
from pydantic import BaseModel
from uiwiz import PageRouter, ui
from uiwiz.frame import Frame

admin_router = PageRouter()


class AdminCredentials(BaseModel):
    username: str
    password: str


@admin_router.page("/admin/login")
async def admin_login_page(request: Request):
    if not admin_auth_configured(request.app.state.admin_settings):
        raise HTTPException(status_code=404, detail="Administrator access is not configured")

    ui.element("h2", "Administrator sign in")
    with ui.form().on_submit(sign_in, swap="outerHTML"):
        ui.input(name="username", placeholder="Administrator username")
        password = ui.input(name="password", placeholder="Administrator password")
        password.attributes["type"] = "password"
        ui.button("Sign in")


@admin_router.ui("/admin/sign-in")
async def sign_in(data: AdminCredentials, request: Request, response: Response):
    settings = request.app.state.admin_settings
    if not admin_auth_configured(settings):
        raise HTTPException(status_code=404, detail="Administrator access is not configured")

    username_matches = compare_digest(data.username, settings.admin_username)
    password_matches = compare_digest(data.password, settings.admin_password)
    if not (username_matches and password_matches):
        ui.toast("Administrator credentials were not accepted").error()
        return Response(
            content=Frame.get_stack().render(),
            status_code=401,
            headers={"cache-control": "no-store", "x-uiwiz-content": "partial-ui"},
            media_type="text/html",
        )

    request.session.clear()
    request.session["admin_authenticated"] = True
    response.headers["HX-Push-Url"] = "/match"
    ui.toast("Signed in as administrator").success()

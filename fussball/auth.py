from config import Settings
from fastapi import HTTPException, Request


def admin_auth_configured(settings: Settings) -> bool:
    return bool(settings.admin_username and settings.admin_password and settings.admin_session_secret)


def require_admin(request: Request) -> None:
    settings: Settings = request.app.state.admin_settings
    if not admin_auth_configured(settings):
        raise HTTPException(status_code=404, detail="Administrator access is not configured")
    if not request.session.get("admin_authenticated"):
        raise HTTPException(status_code=401, detail="Administrator sign-in required")

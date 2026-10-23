from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None
    port: str | None = None
    database_type: Literal["postgresql", "sqlite"] = "sqlite"
    admin_username: str | None = None
    admin_password: str | None = None
    admin_session_secret: str | None = None
    admin_session_cookie_secure: bool = True


settings = Settings()

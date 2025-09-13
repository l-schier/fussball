from pydantic_settings import BaseSettings 


class Settings(BaseSettings):
    host: str
    database: str
    user: str
    password: str
    port: str
    env: str = "dev"

settings = Settings()
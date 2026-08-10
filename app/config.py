"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """HareloStock API configuration.

    All values can be overridden via environment variables or a `.env` file.
    """

    app_name: str = "HareloStock API"
    app_version: str = "0.3.0"
    debug: bool = False

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # CORS — allow all by default for dev; lock down in production
    cors_origins: list[str] = ["*"]

    # Persistence. SQLite works out of the box for local demos; production can
    # point the same application at PostgreSQL with HARELO_DATABASE_URL.
    database_url: str = "sqlite+pysqlite:///./harelostock.db"
    database_echo: bool = False
    auto_create_schema: bool = True

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        # Avoid collisions with generic host variables such as DEBUG or PORT.
        "env_prefix": "HARELO_",
        "extra": "ignore",
    }


settings = Settings()

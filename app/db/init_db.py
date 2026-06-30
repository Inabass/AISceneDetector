from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import engine


def init_development_environment() -> None:
    settings = get_settings()
    configure_logging(settings)
    settings.ensure_data_directories()

    if settings.database_url.startswith("sqlite"):
        with engine.begin() as connection:
            connection.execute(text("PRAGMA journal_mode=WAL"))


if __name__ == "__main__":
    init_development_environment()

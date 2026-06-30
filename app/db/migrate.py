from alembic import command
from alembic.config import Config

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init_db import init_development_environment


def get_alembic_config() -> Config:
    settings = get_settings()
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


def upgrade_database(revision: str = "head") -> None:
    settings = get_settings()
    configure_logging(settings)
    init_development_environment()
    command.upgrade(get_alembic_config(), revision)


if __name__ == "__main__":
    upgrade_database()

"""Ensure PostgreSQL schema exists locally."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

from src.database.connection import Base, db


def init_database() -> None:
    """Create all SQLAlchemy-managed tables in PostgreSQL."""

    logger.info("Ensuring PostgreSQL schema is up-to-date...")
    Base.metadata.create_all(db.engine)
    logger.info("All tables are ready in database {db}", db=db.settings.postgres_db)


if __name__ == "__main__":
    init_database()

"""Simple connectivity test for the PostgreSQL layer."""
from __future__ import annotations

import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from sqlalchemy import text

from src.database.connection import db


def main() -> None:
    logger.info("Checking PostgreSQL connection ...")
    try:
        with db.engine.connect() as conn:
            server_version = conn.exec_driver_sql("SHOW server_version").scalar()
            current_db = conn.exec_driver_sql("SELECT current_database()").scalar()
            search_path = conn.exec_driver_sql("SHOW search_path").scalar()
            ping = conn.execute(text("SELECT 1")).scalar()

        logger.success(
            "Connected to database '{db}' (version {version}); search_path={search_path}; ping={ping}",
            db=current_db,
            version=server_version,
            search_path=search_path,
            ping=ping,
        )
    except Exception as exc:
        logger.error("PostgreSQL connectivity test failed: {error}", error=exc)
        raise


if __name__ == "__main__":
    main()

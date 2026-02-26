"""
Database configuration and session management using SQLAlchemy.

This module sets up the SQLite database connection and provides
session factory for database operations. Uses SQLAlchemy ORM for
clean, type-safe database access.
"""

import os
import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Database URL - SQLite for simplicity
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./financial_analyzer.db",
)

# Create engine with proper SQLite settings
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,  # Set to True for SQL query logging
)

# Enable SQLite foreign keys
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        logger.debug("SQLite PRAGMA foreign_keys enabled")

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Base class for models
Base = declarative_base()


def get_session() -> Session:
    """
    Get a database session for FastAPI dependency injection.
    
    This is a generator that properly closes the session after use.
    FastAPI will call this for each request and cleanup via finally.

    Usage in endpoint:
        async def my_endpoint(session: Session = Depends(get_session)):
            ...

    Yields:
        Session: SQLAlchemy session instance
    """
    db = SessionLocal()
    logger.info(f"[DB] Opening session: {id(db)}")
    try:
        yield db
    except Exception as e:
        logger.error(f"[DB] Error in session {id(db)}: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()
        logger.info(f"[DB] Closed session: {id(db)}")


def init_db():
    """
    Initialize database by creating all tables.

    Call this once at application startup.
    """
    logger.info("[DB] Initializing database...")
    Base.metadata.create_all(bind=engine)
    logger.info(f"[DB] Database initialized: {DATABASE_URL}")
    print(f"✓ Database initialized: {DATABASE_URL}")

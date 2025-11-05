"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Create engine
engine = create_engine(
    settings.database_url,
    connect_args={
        "check_same_thread": False,  # Needed for SQLite
        "timeout": 30  # Increase timeout for file locks
    },
    pool_pre_ping=True  # Verify connections before using
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


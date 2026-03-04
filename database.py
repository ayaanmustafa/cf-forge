# backend/database.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Use DATABASE_URL from environment (Render provides this)
# For local development, use: postgresql://user:password@localhost/cf_forge
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost/cf_forge"
)

# Handle Render's postgres:// protocol (needs to be postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,           # Health check before using connection
    pool_size=5,                   # Connections to keep in pool
    max_overflow=5,                # Additional connections beyond pool_size
    pool_recycle=3600,             # Recycle connections after 1 hour
    pool_timeout=30,               # Wait up to 30 seconds for a connection
    echo=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()
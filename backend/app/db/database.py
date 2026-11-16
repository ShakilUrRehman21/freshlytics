import logging
import ssl

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from app.core.config import settings

logger = logging.getLogger(__name__)

connect_args: dict = {}
engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}

if settings.is_postgres:
    # Poolers such as Neon's / PgBouncer (transaction mode) don't support
    # asyncpg's prepared-statement cache.
    connect_args["statement_cache_size"] = 0
    connect_args["prepared_statement_cache_size"] = 0
    if settings.use_ssl:
        connect_args["ssl"] = ssl.create_default_context()
    engine_kwargs.update(pool_size=5, max_overflow=5, pool_recycle=300)
elif settings.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_async_engine(settings.SQLALCHEMY_DATABASE_URI, connect_args=connect_args, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# Columns added after the first release. create_all() never alters existing
# tables, so add anything missing (lightweight, idempotent migration).
_ADDED_COLUMNS = {
    "scans": {
        "rot_probability": "FLOAT",
        "storage_type": "VARCHAR(16)",
        "fruit_source": "VARCHAR(16)",
        "thumbnail": "TEXT",
        "heatmap": "TEXT",
        "notes": "TEXT",
    },
}


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def existing(sync_conn):
            insp = inspect(sync_conn)
            return {t: {c["name"] for c in insp.get_columns(t)} for t in _ADDED_COLUMNS if insp.has_table(t)}

        cols = await conn.run_sync(existing)
        for table, wanted in _ADDED_COLUMNS.items():
            for name, ddl in wanted.items():
                if name not in cols.get(table, set()):
                    logger.info("Adding column %s.%s", table, name)
                    await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))

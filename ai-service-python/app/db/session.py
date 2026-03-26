from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(
    settings.database_connection_string,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)


# FreeTDS needs explicit TEXTSIZE to handle large NVARCHAR(MAX) writes
@event.listens_for(engine.sync_engine, "connect")
def _set_textsize(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET TEXTSIZE 2147483647")
    cursor.close()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

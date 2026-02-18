import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Use a dedicated data folder for persistence (important for Docker volumes)
    db_path = "/app/data/test.db" if os.path.exists("/app/data") else "./test.db"
    DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"
elif DATABASE_URL.startswith("postgres://"):
    # SQLAlchemy requires postgresql://
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

class Base(DeclarativeBase):
    pass

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Simple migration: add is_admin if not exists
        # In a real prod env, use Alembic. Here we do a manual check.
        from sqlalchemy import text
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
            await conn.commit()
        except:
            # Column likely exists
            pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

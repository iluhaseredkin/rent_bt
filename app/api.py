import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import select

from app.database import AsyncSessionLocal, init_db, get_db
from app.models import Channel, User

# Import new routers
from app.routers import client, admin

logger = logging.getLogger(__name__)

async def seed_data():
    """Seed initial data if empty (e.g. admin user, default channels)."""
    async with AsyncSessionLocal() as session:
        # Check if we have channels
        res = await session.execute(select(Channel))
        if not res.first():
            logger.info("Seeding default channels...")
            from app.parser import CITY_MAPPING # Legacy import just to get list
            # We need to invert CITY_MAPPING or just hardcode some defaults
            # Actually better to just let parser fail or wait for admin to add.
            # But let's add some defaults to avoid empty state.
            defaults = [
                ("batumi_appartaments", "Batumi"),
                ("tbilisi_rent", "Tbilisi"), 
                # Add more real ones if known
            ]
            for username, city in defaults:
                session.add(Channel(username=username, city=city))
            await session.commit()

@asynccontextmanager
async def lifespan(application: FastAPI):
    await init_db()
    # await seed_data() # Optional: seed if needed
    logger.info("Mini App DB initialized.")
    yield

app = FastAPI(title="Rent Mini App API", lifespan=lifespan)

# CORS — allow Telegram WebApp origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(client.router)
app.include_router(admin.router)

# --- Static files ---
WEB_APP_DIR = Path(__file__).resolve().parent.parent / "web_app"

@app.get("/")
async def serve_index():
    return FileResponse(WEB_APP_DIR / "index.html")

# Mount static after the root route so index.html takes priority
app.mount("/static", StaticFiles(directory=WEB_APP_DIR), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

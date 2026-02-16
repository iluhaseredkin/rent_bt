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
    """Seed initial data if empty (e.g. default channels)."""
    async with AsyncSessionLocal() as session:
        # Check if we have channels
        res = await session.execute(select(Channel))
        if not res.first():
            logger.info("Seeding default channels...")
            city_mapping = {
                'batumi_arendaa': 'Batumi', 'kvartiravbatumi': 'Batumi',
                'kobuletiarenda': 'Kobuleti', 'arenda_v_tbilise': 'Tbilisi',
                'tbilisi_arendaa': 'Tbilisi', 'alaniya_arenda': 'Alanya',
                'apartamenty_alanya': 'Alanya', 'alania_tipical': 'Alanya',
                'antaliya_arenda': 'Antalya', 'Antalya_realestates': 'Antalya',
                'stambyl_arenda': 'Istanbul', 'Istanbul_shat': 'Istanbul',
                'novisad_stan': 'NoviSad', 'erevan_kvartira': 'Yerevan',
                'standardrealty': 'Yerevan', 'kvartiraverevane1': 'Yerevan',
                'chernogoria_realty': 'Montenegro', 'Montenegro_sell_rent': 'Montenegro',
                'serbiya_arenda': 'Serbia', 'rentalserbia': 'Serbia',
                'beograd_stan': 'Belgrade', 'flattorentbelgrade': 'Belgrade',
                'fethiye_rent': 'Fethiye', 'housemarmaris': 'Marmaris',
                'rentinlisbon': 'Lisbon', 'belkaspain': 'Barcelona'
            }
            for username, city in city_mapping.items():
                session.add(Channel(username=username, city=city))
            await session.commit()

@asynccontextmanager
async def lifespan(application: FastAPI):
    await init_db()
    await seed_data()
    logger.info("Mini App DB initialized and seeded.")
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

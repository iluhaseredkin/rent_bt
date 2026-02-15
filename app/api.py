import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select, func, distinct
from pathlib import Path

from .database import AsyncSessionLocal, init_db
from .models import Listing

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    await init_db()
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

# --- Static files ---
WEB_APP_DIR = Path(__file__).resolve().parent.parent / "web_app"


@app.get("/")
async def serve_index():
    return FileResponse(WEB_APP_DIR / "index.html")


# Mount static after the root route so index.html takes priority
app.mount("/static", StaticFiles(directory=WEB_APP_DIR), name="static")


# --- API endpoints ---

@app.get("/api/cities")
async def get_cities():
    """Return sorted list of unique cities from DB."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(distinct(Listing.city)).where(Listing.city.isnot(None))
        )
        cities = sorted([row[0] for row in result.all()])
    return {"cities": cities}


@app.get("/api/listings")
async def get_listings(
    city: str | None = Query(None),
    min_price: float = Query(0, ge=0),
    max_price: float = Query(100_000, ge=0),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """Return filtered and paginated listings."""
    async with AsyncSessionLocal() as session:
        q = select(Listing).where(
            Listing.price_usd.isnot(None),
            Listing.price_usd >= min_price,
            Listing.price_usd <= max_price,
        )
        count_q = select(func.count(Listing.id)).where(
            Listing.price_usd.isnot(None),
            Listing.price_usd >= min_price,
            Listing.price_usd <= max_price,
        )

        if city:
            q = q.where(Listing.city == city)
            count_q = count_q.where(Listing.city == city)

        if search:
            # Case-insensitive search
            pattern = f"%{search}%"
            q = q.where(Listing.text.ilike(pattern))
            count_q = count_q.where(Listing.text.ilike(pattern))

        # Total count
        total = (await session.execute(count_q)).scalar() or 0

        # Paginated results
        offset = (page - 1) * per_page
        result = await session.execute(
            q.order_by(Listing.date.desc()).offset(offset).limit(per_page)
        )
        listings = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page else 1,
        "listings": [
            {
                "id": l.id,
                "city": l.city,
                "price_usd": l.price_usd,
                "price_original": l.price_original,
                "currency": l.currency,
                "date": l.date.isoformat() if l.date else None,
                "text": (l.text[:300] + "…") if l.text and len(l.text) > 300 else l.text,
                "link": l.link,
                "channel": l.channel_username,
            }
            for l in listings
        ],
    }


@app.get("/api/histogram")
async def get_histogram(city: str | None = Query(None)):
    """Return histogram data for price distribution."""
    async with AsyncSessionLocal() as session:
        # Filter by city if provided, otherwise all
        q = select(Listing.price_usd).where(Listing.price_usd.isnot(None))
        if city:
            q = q.where(Listing.city == city)
        
        result = await session.execute(q)
        prices = [p for p in result.scalars().all() if p > 0]
        
    if not prices:
        return {"labels": [], "data": []}
        
    # Remove top 5% outliers for better chart visualization
    prices.sort()
    cutoff_idx = int(len(prices) * 0.95)
    if cutoff_idx > 0:
        prices = prices[:cutoff_idx]
    
    if not prices:
        return {"labels": [], "data": []}

    min_p = 0
    max_p = prices[-1]
    if max_p < 100: max_p = 100
    
    # 15 bins
    bin_count = 15
    step = (max_p - min_p) / bin_count
    
    bins = [0] * bin_count
    labels = []
    
    for i in range(bin_count):
        low = min_p + i * step
        high = low + step
        labels.append(f"{int(low)}-{int(high)}")
        
    for p in prices:
        # Calculate bin index
        idx = int((p - min_p) / step)
        # Handle edge case for max value (put in last bin)
        if idx >= bin_count:
            idx = bin_count - 1
        if 0 <= idx < bin_count:
            bins[idx] += 1
            
    return {"labels": labels, "data": bins}


@app.get("/api/stats")
async def get_stats():
    """Return overall statistics."""
    async with AsyncSessionLocal() as session:
        total = (await session.execute(select(func.count(Listing.id)))).scalar() or 0
        min_price = (
            await session.execute(
                select(func.min(Listing.price_usd)).where(Listing.price_usd.isnot(None))
            )
        ).scalar()
        max_price = (
            await session.execute(
                select(func.max(Listing.price_usd)).where(Listing.price_usd.isnot(None))
            )
        ).scalar()
        cities_count = (
            await session.execute(
                select(func.count(distinct(Listing.city))).where(Listing.city.isnot(None))
            )
        ).scalar() or 0

    return {
        "total_listings": total,
        "cities_count": cities_count,
        "min_price": min_price,
        "max_price": max_price,
    }

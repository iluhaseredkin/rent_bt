from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models import Listing, Suggestion, User
from app.auth import verify_telegram_authorization

router = APIRouter(prefix="/api", tags=["client"])

# --- Models ---
class SuggestionRequest(BaseModel):
    type: str  # listing, source
    content: str
    city: str | None = None

# --- Endpoints ---

@router.get("/cities")
async def get_cities(session: AsyncSession = Depends(get_db)):
    """Return sorted list of unique cities from DB."""
    result = await session.execute(
        select(distinct(Listing.city)).where(Listing.city.isnot(None))
    )
    cities = sorted([row[0] for row in result.all()])
    return {"cities": cities}

@router.get("/listings")
async def get_listings(
    city: str | None = Query(None),
    min_price: float = Query(0, ge=0),
    max_price: float = Query(100_000, ge=0),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db)
):
    """Return filtered and paginated listings."""
    
    # Optimization: Require city if searching to prevent heavy scans
    if search and not city:
        raise HTTPException(status_code=400, detail="City selection is required for search.")

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

@router.get("/histogram")
async def get_histogram(city: str | None = Query(None), session: AsyncSession = Depends(get_db)):
    """Return histogram data for price distribution."""
    # Filter by city if provided, otherwise all
    q = select(Listing.price_usd).where(Listing.price_usd.isnot(None))
    if city:
        q = q.where(Listing.city == city)
    
    # Stream results to avoid loading all into memory at once
    # Using stream scalars to handle large datasets
    prices = []
    result = await session.stream(q)
    async for p in result.scalars():
            if p > 0:
                prices.append(p)
    
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
        if step > 0:
            idx = int((p - min_p) / step)
            # Handle edge case for max value (put in last bin)
            if idx >= bin_count:
                idx = bin_count - 1
            if 0 <= idx < bin_count:
                bins[idx] += 1
            
    return {"labels": labels, "data": bins}

@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_db)):
    """Return overall statistics."""
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

@router.post("/suggest")
async def submit_suggestion(
    suggestion: SuggestionRequest,
    user: User = Depends(verify_telegram_authorization),
    session: AsyncSession = Depends(get_db)
):
    """
    Submit a suggestion or direct listing (SECURED).
    """
    if suggestion.type == "listing":
        # 1. Direct parsing of the ad text
        from app.parser import extract_prices, detect_currency, convert_to_usd
        
        price = extract_prices(suggestion.content)
        currency = detect_currency(suggestion.content)
        usd_price = convert_to_usd(price, currency)
        
        if not price or not usd_price:
             raise HTTPException(status_code=400, detail="Could not extract price from text. Please ensure price is clearly mentioned.")

        # 2. Add as a direct listing
        import time
        new_listing = Listing(
            channel_username="user_post",
            date=func.now(),
            text=suggestion.content,
            link=f"user_{user.user_id}_{int(time.time())}", # Unique pseudo link
            price_original=price,
            currency=currency,
            price_usd=usd_price,
            city=suggestion.city or "Unknown"
        )
        session.add(new_listing)
        await session.commit()
        return {"status": "ok", "message": "Listing published!"}

    elif suggestion.type == "source":
        # Save to suggestions for admin approval
        new_suggestion = Suggestion(
            user_id=user.user_id,
            type="source",
            content=suggestion.content,
            status="pending"
        )
        session.add(new_suggestion)
        await session.commit()
        return {"status": "ok", "message": "Source suggestion submitted for approval"}

    else:
        # Fallback for other types
        new_suggestion = Suggestion(
            user_id=user.user_id,
            type=suggestion.type,
            content=suggestion.content,
            status="pending"
        )
        session.add(new_suggestion)
        await session.commit()
        return {"status": "ok", "message": "Suggestion submitted"}

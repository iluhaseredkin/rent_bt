import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.models import Listing, Suggestion, User, Channel
from app.auth import get_current_admin
from app.parser import run_parser

router = APIRouter(prefix="/api/admin", tags=["admin"])

# --- Models ---
class SuggestionResponse(BaseModel):
    id: int
    user_id: int
    type: str
    content: str
    status: str
    created_at: datetime
    # user_username: str | None = None # Would need join

class StatsResponse(BaseModel):
    total_users: int
    active_users_24h: int
    total_channels: int
    error_channels: int
    pending_suggestions: int

class ChannelResponse(BaseModel):
    id: int
    username: str
    city: str
    status: str
    error_count: int
    last_parsed_at: datetime | None

class ApproveRequest(BaseModel):
    action: str = "approve" # approve / reject

# --- Endpoints ---

@router.get("/stats", response_model=StatsResponse)
async def get_admin_stats(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Get dashboard stats (SECURED: Admin only).
    """
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(days=1)
    
    total_users = (await session.execute(select(func.count(User.user_id)))).scalar() or 0
    active_users = (await session.execute(
        select(func.count(User.user_id)).where(User.last_interaction >= day_ago)
    )).scalar() or 0
    
    total_channels = (await session.execute(select(func.count(Channel.id)))).scalar() or 0
    error_channels = (await session.execute(
        select(func.count(Channel.id)).where(Channel.status == 'error')
    )).scalar() or 0
    
    pending_sugg = (await session.execute(
        select(func.count(Suggestion.id)).where(Suggestion.status == 'pending')
    )).scalar() or 0
    
    return {
        "total_users": total_users,
        "active_users_24h": active_users,
        "total_channels": total_channels,
        "error_channels": error_channels,
        "pending_suggestions": pending_sugg
    }

@router.get("/channels", response_model=List[ChannelResponse])
async def get_channels(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """List all monitored channels and status."""
    result = await session.execute(select(Channel).order_by(Channel.status, Channel.username))
    return result.scalars().all()

@router.get("/suggestions", response_model=List[SuggestionResponse])
async def get_suggestions(
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """List pending suggestions."""
    result = await session.execute(
        select(Suggestion)
        .where(Suggestion.status == 'pending')
        .order_by(Suggestion.created_at.desc())
    )
    return result.scalars().all()

@router.post("/suggestions/{id}/{action}")
async def moderate_suggestion(
    id: int,
    action: str,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """
    Approve or Reject a suggestion.
    action: 'approve' | 'reject'
    """
    if action not in ['approve', 'reject']:
        raise HTTPException(status_code=400, detail="Invalid action")
        
    result = await session.execute(select(Suggestion).where(Suggestion.id == id))
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
        
    if action == 'reject':
        suggestion.status = 'rejected'
        await session.commit()
        return {"status": "rejected"}
        
    if action == 'approve':
        suggestion.status = 'approved'
        
        if suggestion.type == 'source':
            # Expected format: "@username - City"
            parts = suggestion.content.split(" - ")
            if len(parts) >= 2:
                username = parts[0].strip().replace("@", "")
                city = parts[1].strip()
                
                # Add if not exists
                res = await session.execute(select(Channel).where(Channel.username == username))
                if not res.scalar_one_or_none():
                    new_ch = Channel(username=username, city=city)
                    session.add(new_ch)
        
        elif suggestion.type == 'listing':
            try:
                data = json.loads(suggestion.content)
                import time
                new_listing = Listing(
                    channel_username="user_post",
                    date=func.now(),
                    text=data.get("text"),
                    link=f"user_{suggestion.user_id}_{int(time.time())}",
                    price_original=data.get("price"),
                    currency="USD", # Default to USD for direct posts for now
                    price_usd=data.get("price"),
                    city=data.get("city", "Unknown")
                )
                session.add(new_listing)
            except Exception as e:
                # Log or handle error
                pass

    await session.commit()
    return {"status": "approved"}
    
@router.post("/channels")
async def add_channel(
    username: str,
    city: str,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """Manually add a channel."""
    # Check exists
    res = await session.execute(select(Channel).where(Channel.username == username))
    if res.scalar_one_or_none():
         raise HTTPException(status_code=400, detail="Channel already exists")
         
    new_ch = Channel(username=username, city=city)
    session.add(new_ch)
    await session.commit()
    return {"status": "created", "id": new_ch.id}

@router.delete("/channels/{id}")
async def delete_channel(
    id: int,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db)
):
    """Delete a channel."""
    result = await session.execute(select(Channel).where(Channel.id == id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    await session.delete(channel)
    await session.commit()
    return {"status": "deleted"}

@router.post("/run_parser")
async def trigger_parser(
    admin: User = Depends(get_current_admin)
):
    """Trigger manual database update (Admin only)."""
    try:
        await run_parser()
        return {"status": "ok", "message": "База успешно обновлена!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

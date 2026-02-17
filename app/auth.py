import os
import hmac
import hashlib
import json
from urllib.parse import parse_qsl
from fastapi import Header, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.database import get_db
from app.models import User

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID") # Can be a single ID or comma-separated string


async def verify_telegram_authorization(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db)
) -> User:
    """
    Verifies Telegram's initData string (passed in Authorization header).
    Returns the User object from DB (creates if not exists).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="BOT_TOKEN not configured")

    try:
        # 1. Parse query string
        init_data = dict(parse_qsl(authorization))
        
        if "hash" not in init_data:
             raise HTTPException(status_code=401, detail="Hash missing")
             
        received_hash = init_data.pop("hash")
        
        # 2. Sort keys
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(init_data.items())
        )
        
        # 3. Calculate hash
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calculated_hash != received_hash:
            raise HTTPException(status_code=403, detail="Invalid hash")
            
        # 4. Get User data
        user_data = json.loads(init_data["user"])
        user_id = user_data["id"]
        
        # 5. Fetch or Create User in DB
        result = await session.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()
        
        # Check if user is admin by ENV
        is_env_admin = False
        if ADMIN_ID:
            try:
                admin_ids = [int(i.strip()) for i in ADMIN_ID.split(",") if i.strip()]
                if user_id in admin_ids:
                    is_env_admin = True
            except ValueError:
                pass

        if not user:
            # Should have been created by bot /start, but IF NOT, create here
            user = User(
                user_id=user_id,
                username=user_data.get("username"),
                first_name=user_data.get("first_name"),
                is_active=True,
                is_admin=is_env_admin
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        elif is_env_admin and not user.is_admin:
            # Update user if they become admin via ENV
            user.is_admin = True
            await session.commit()
            
        return user

    except Exception as e:
        # logger.error(f"Auth failed: {e}")
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

async def get_current_admin(user: User = Depends(verify_telegram_authorization)) -> User:
    # Check both DB flag and environment variable
    is_env_admin = False
    if ADMIN_ID:
        try:
            admin_ids = [int(i.strip()) for i in ADMIN_ID.split(",") if i.strip()]
            if user.user_id in admin_ids:
                is_env_admin = True
        except ValueError:
            pass

    if not user.is_admin and not is_env_admin:
        print(f"DEBUG: Admin check FAILED for user_id={user.user_id}. ADMIN_ID env: {ADMIN_ID}")
        raise HTTPException(status_code=403, detail="Admin privileges required")
    
    # If it's an env admin but not marked in DB, we could optionally update DB here
    # but for read-only check it's enough.
    return user

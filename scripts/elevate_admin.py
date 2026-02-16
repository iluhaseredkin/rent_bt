import asyncio
import sys
from app.database import AsyncSessionLocal, init_db
from app.models import User
from sqlalchemy import update, select

async def elevate(user_id: int):
    # Ensure DB and tables exist
    await init_db()
    
    async with AsyncSessionLocal() as session:
        # Check if user exists
        res = await session.execute(select(User).where(User.user_id == user_id))
        user = res.scalar_one_or_none()
        
        if user:
            user.is_admin = True
            print(f"User {user_id} ({user.username}) is now an admin.")
        else:
            # Create user if not exists
            new_user = User(
                user_id=user_id,
                username="Admin",
                first_name="Admin",
                is_admin=True
            )
            session.add(new_user)
            print(f"User {user_id} not found. Created new user and set as admin.")
            
        await session.commit()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/elevate_admin.py <TELEGRAM_USER_ID>")
        sys.exit(1)
    
    uid = int(sys.argv[1])
    asyncio.run(elevate(uid))

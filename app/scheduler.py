from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

# Single scheduler instance
scheduler = AsyncIOScheduler()

async def get_setting(session, key, default):
    from app.models import Setting
    result = await session.execute(select(Setting).where(Setting.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else default

async def update_scheduler_jobs():
    """Reload jobs from DB settings."""
    from app.database import AsyncSessionLocal
    from app.parser import run_parser
    from app.bot import send_daily_notifications
    
    async with AsyncSessionLocal() as session:
        # 1. Parser Job
        mode = await get_setting(session, 'parser_mode', 'interval')
        
        # Remove if exists
        if scheduler.get_job('parser_job'):
            scheduler.remove_job('parser_job')
            
        if mode == 'interval':
            hours = int(await get_setting(session, 'parser_interval_hours', '6'))
            if hours > 0:
                scheduler.add_job(run_parser, 'interval', hours=hours, id='parser_job')
                logger.info(f"Scheduler: Parser set to interval ({hours}h)")
        elif mode == 'daily':
            time_str = await get_setting(session, 'parser_daily_time', '03:00')
            try:
                hour, minute = map(int, time_str.split(':'))
                scheduler.add_job(run_parser, 'cron', hour=hour, minute=minute, id='parser_job')
                logger.info(f"Scheduler: Parser set to daily at {time_str} UTC")
            except Exception as e:
                logger.error(f"Invalid daily time format: {time_str}")
        else:
            logger.info("Scheduler: Parser set to manual mode")

        # 2. Notification Job (Constant but we keep it here for central management)
        if not scheduler.get_job('notification_job'):
            scheduler.add_job(send_daily_notifications, 'cron', hour=10, minute=0, id='notification_job')
            logger.info("Scheduler: Notifications scheduled daily at 10:00 UTC")

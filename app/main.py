import asyncio
import logging
import sys
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import init_db
from app.parser import run_parser
from app.bot import bot, dp, send_daily_notifications

# Setup logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting application...")
    
    # Initialize Database
    await init_db()
    logger.info("Database initialized.")

    # Setup Scheduler
    scheduler = AsyncIOScheduler()
    
    # Run parser every 6 hours
    scheduler.add_job(run_parser, 'interval', hours=6, id='parser_job')
    
    # Run notifications daily at 10:00 UTC
    scheduler.add_job(send_daily_notifications, 'cron', hour=10, minute=0, id='notification_job')
    
    scheduler.start()
    logger.info("Scheduler started.")

    # Optional: Run parser immediately on startup if needed (uncomment if desired)
    # logger.info("Running initial parse...")
    # asyncio.create_task(run_parser())

    # Start Bot Polling
    logger.info("Starting bot polling...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application stopped.")

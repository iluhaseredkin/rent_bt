import asyncio
import logging
import sys
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import init_db
from app.parser import run_parser
from app.bot import bot, dp, send_daily_notifications
from app.api import app as fastapi_app

# Setup logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def run_api_server():
    """Run FastAPI server in the background."""
    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


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

    # Start FastAPI server in background task
    api_task = asyncio.create_task(run_api_server())
    logger.info("Mini App API started on http://0.0.0.0:8000")

    # Start Bot Polling
    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        api_task.cancel()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application stopped.")

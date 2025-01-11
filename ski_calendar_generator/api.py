from fastapi import FastAPI, Response, BackgroundTasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from contextlib import asynccontextmanager

from ski_calendar_generator.calendar_generator import CalendarGenerator
from ski_calendar_generator.ski_data_fetcher import SkiDataFetcher

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Scheduler setup
scheduler = AsyncIOScheduler()

async def scheduled_refresh():
    """Function to be called by the scheduler"""
    fetcher = SkiDataFetcher()
    await fetcher.fetch_all_details(force_refresh=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the scheduler
    scheduler.add_job(
        scheduled_refresh,
        CronTrigger(hour=3),  # Run at 3 AM every day
        id="refresh_calendar",
        name="Refresh Ski Calendar Data"
    )
    scheduler.start()
    logger.info("Scheduler started")
    
    # Perform initial data fetch
    fetcher = SkiDataFetcher()
    await fetcher.fetch_all_details()
    
    yield
    
    # Shutdown scheduler
    scheduler.shutdown()
    logger.info("Scheduler shutdown")

# FastAPI application
app = FastAPI(lifespan=lifespan)

@app.get("/calendar.ics")
async def get_calendar():
    generator = CalendarGenerator()
    calendar_data = generator.generate_ical()
    
    return Response(
        content=calendar_data,
        media_type="text/calendar",
        headers={
            "Content-Disposition": "attachment; filename=ski-calendar.ics"
        }
    )

@app.get("/refresh")
async def refresh_data(background_tasks: BackgroundTasks):
    """Endpoint to force refresh of competition data"""
    background_tasks.add_task(scheduled_refresh)
    return {
        "status": "success",
        "message": "Refresh started in background"
    }

@app.get("/scheduler/status")
async def scheduler_status():
    """Endpoint to check scheduler status"""
    jobs = scheduler.get_jobs()
    return {
        "scheduler_running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time,
                "trigger": str(job.trigger)
            }
            for job in jobs
        ]
    }

def start():
    """Entry point for the application."""
    import uvicorn
    uvicorn.run("ski_calendar_generator.api:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    start()
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from services.investment import InvestmentService
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.investment_service = InvestmentService()

    def start(self):
        # Run every 5 minutes to check for unlocked investments
        self.scheduler.add_job(
            self.process_locked_investments,
            trigger=IntervalTrigger(minutes=5),
            id='locked_check',
            replace_existing=True
        )

        # Process expired investments every hour
        self.scheduler.add_job(
            self.process_expired_investments,
            trigger=IntervalTrigger(hours=1),
            id='expired_investments',
            replace_existing=True
        )

        # 🔧 Run every hour to fix stuck timers
        self.scheduler.add_job(
            self.correct_timers,
            trigger=IntervalTrigger(hours=1),
            id='timer_correction',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("Scheduler started - checking for unlocked investments every 5 minutes")

    async def process_locked_investments(self):
        try:
            logger.info("Checking for unlocked investments...")
            await self.investment_service.process_locked_investments()
        except Exception as e:
            logger.error(f"Error processing locked investments: {e}")

    def process_expired_investments(self):
        try:
            logger.info("Checking for expired investments...")
            self.investment_service.process_expired_investments()
        except Exception as e:
            logger.error(f"Error processing expired investments: {e}")

    def correct_timers(self):
        """Auto-correct stuck timers (runs every hour)"""
        try:
            logger.info("🔄 Running timer correction job...")
            # For the new system, this will check if any investments are stuck
            # and correct their unlock dates
            self.investment_service.correct_stuck_timers()
        except Exception as e:
            logger.error(f"Error in timer correction: {e}")

    def stop(self):
        self.scheduler.shutdown()

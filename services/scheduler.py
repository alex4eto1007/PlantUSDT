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
        # Run every 5 minutes to check for due payouts
        self.scheduler.add_job(
            self.process_daily_payouts,
            trigger=IntervalTrigger(minutes=5),
            id='payout_check',
            replace_existing=True
        )

        # Process expired investments every hour
        self.scheduler.add_job(
            self.process_expired_investments,
            trigger=IntervalTrigger(hours=1),
            id='expired_investments',
            replace_existing=True
        )

        # 🔧 NEW: Run every hour to fix stuck timers
        self.scheduler.add_job(
            self.correct_timers,
            trigger=IntervalTrigger(hours=1),
            id='timer_correction',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("Scheduler started - checking for due payouts every 5 minutes, correcting timers every hour")

    async def process_daily_payouts(self):
        try:
            logger.info("Checking for due payouts...")
            await self.investment_service.process_daily_payouts()
        except Exception as e:
            logger.error(f"Error processing daily payouts: {e}")

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
            self.investment_service.correct_stuck_timers()
        except Exception as e:
            logger.error(f"Error in timer correction: {e}")

    def stop(self):
        self.scheduler.shutdown()

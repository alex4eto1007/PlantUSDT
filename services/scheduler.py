from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from services.investment import InvestmentService
from services.deposit_scanner import DepositScanner
from services.referral import check_missed_active_referrals
from scripts.fix_missing_referral_rewards import fix_missing_referral_rewards
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.investment_service = InvestmentService()
        self.deposit_scanner = DepositScanner()

    def start(self):
        self.scheduler.add_job(
            self.process_locked_investments,
            trigger=IntervalTrigger(minutes=5),
            id='locked_check',
            replace_existing=True
        )

        self.scheduler.add_job(
            self.scan_deposits,
            trigger=IntervalTrigger(minutes=5),
            id='deposit_scanner',
            replace_existing=True
        )

        self.scheduler.add_job(
            self.process_expired_investments,
            trigger=IntervalTrigger(hours=1),
            id='expired_investments',
            replace_existing=True
        )

        self.scheduler.add_job(
            self.correct_timers,
            trigger=IntervalTrigger(hours=1),
            id='timer_correction',
            replace_existing=True
        )

        # Daily check for missed active referrals at midnight UTC
        self.scheduler.add_job(
            self.check_missed_active_referrals,
            trigger=CronTrigger(hour=0, minute=0),
            id='check_missed_active_referrals',
            replace_existing=True
        )

        # ✅ NEW: Daily check for missing referral rewards at midnight UTC
        self.scheduler.add_job(
            self.check_missing_referral_rewards,
            trigger=CronTrigger(hour=0, minute=0),
            id='check_missing_referral_rewards',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("Scheduler started - checking for unlocked investments every 5 minutes")
        logger.info("🔍 Polygon deposit scanner running every 5 minutes")
        logger.info("🔄 Active referral catch-up check scheduled daily at 00:00 UTC")
        logger.info("🎁 Referral rewards check scheduled daily at 00:00 UTC")

    async def process_locked_investments(self):
        try:
            logger.info("Checking for unlocked investments on Polygon...")
            await self.investment_service.process_locked_investments()
        except Exception as e:
            logger.error(f"Error processing locked investments: {e}")

    async def scan_deposits(self):
        try:
            logger.info("🔍 Scanning for Polygon deposits...")
            pass
        except Exception as e:
            logger.error(f"Error scanning Polygon deposits: {e}")

    def process_expired_investments(self):
        try:
            logger.info("Checking for expired investments on Polygon...")
            pass
        except Exception as e:
            logger.error(f"Error processing expired investments: {e}")

    def correct_timers(self):
        try:
            logger.info("🔄 Running timer correction job on Polygon...")
            pass
        except Exception as e:
            logger.error(f"Error in timer correction: {e}")

    def check_missed_active_referrals(self):
        try:
            logger.info("🔄 Running daily catch-up for missed active referrals...")
            check_missed_active_referrals()
        except Exception as e:
            logger.error(f"Error checking missed active referrals: {e}")

    def check_missing_referral_rewards(self):
        try:
            logger.info("🎁 Running daily check for missing referral rewards...")
            fix_missing_referral_rewards()
            logger.info("✅ Referral rewards check completed")
        except Exception as e:
            logger.error(f"Error checking missing referral rewards: {e}")

    def stop(self):
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

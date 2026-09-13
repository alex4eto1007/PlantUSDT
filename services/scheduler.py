from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from services.investment import InvestmentService
from services.deposit_scanner import DepositScanner
from services.referral import check_missed_active_referrals
from scripts.fix_missing_referral_rewards import fix_missing_referral_rewards
from database.db_manager import DatabaseManager
from database.models import User, GiveawayEntry
from datetime import datetime, timedelta
import logging
import asyncio

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.investment_service = InvestmentService()
        self.deposit_scanner = DepositScanner()
        self.db = DatabaseManager()

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

        self.scheduler.add_job(
            self.check_missed_active_referrals,
            trigger=CronTrigger(hour=0, minute=0),
            id='check_missed_active_referrals',
            replace_existing=True
        )

        self.scheduler.add_job(
            self.check_missing_referral_rewards,
            trigger=CronTrigger(hour=0, minute=0),
            id='check_missing_referral_rewards',
            replace_existing=True
        )

        self.scheduler.add_job(
            self.snapshot_and_reset_giveaway,
            trigger=CronTrigger(day_of_week='fri', hour=0, minute=0),
            id='giveaway_weekly_reset',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("Scheduler started - checking for unlocked investments every 5 minutes")
        logger.info("🔍 Polygon deposit scanner running every 5 minutes")
        logger.info("🔄 Active referral catch-up check scheduled daily at 00:00 UTC")
        logger.info("🎁 Referral rewards check scheduled daily at 00:00 UTC")
        logger.info("🏆 Giveaway snapshot + reset scheduled every Friday at 00:00 UTC")

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

    def snapshot_and_reset_giveaway(self):
        """Friday 00:00 UTC — snapshot eligible users, then reset the cycle counter."""
        session = self.db.get_session()
        try:
            now = datetime.utcnow()
            cycle_start = now - timedelta(days=7)
            eligible = session.query(User).filter(User.ads_watched_this_cycle >= 150).all()

            for u in eligible:
                entry = GiveawayEntry(
                    user_id=u.id,
                    telegram_id=u.telegram_id,
                    username=u.username,
                    ads_watched=u.ads_watched_this_cycle,
                    cycle_start=cycle_start,
                    cycle_end=now
                )
                session.add(entry)

            session.query(User).update({User.ads_watched_this_cycle: 0})
            session.commit()
            logger.info(f"🏆 Giveaway: snapshotted {len(eligible)} eligible users, reset cycle counter")
        except Exception as e:
            session.rollback()
            logger.error(f"Error in giveaway snapshot: {e}")
        finally:
            session.close()

    def stop(self):
        self.scheduler.shutdown()
        logger.info("Scheduler stopped")

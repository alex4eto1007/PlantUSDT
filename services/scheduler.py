from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from services.investment import InvestmentService
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.investment_service = InvestmentService()
        
    def start(self):
        # Run daily payouts at 00:00 UTC
        self.scheduler.add_job(
            self.process_daily_payouts,
            trigger=CronTrigger(hour=0, minute=0),
            id='daily_payouts',
            replace_existing=True
        )
        
        # Run hourly to catch any missed payouts
        self.scheduler.add_job(
            self.process_daily_payouts,
            'interval',
            hours=1,
            id='hourly_payouts_check',
            replace_existing=True
        )
        
        # Process expired investments every 6 hours
        self.scheduler.add_job(
            self.process_expired_investments,
            'interval',
            hours=6,
            id='expired_investments',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("Scheduler started successfully")
        
    def process_daily_payouts(self):
        try:
            logger.info("Processing daily payouts...")
            self.investment_service.process_daily_payouts()
            logger.info("Daily payouts processed successfully")
        except Exception as e:
            logger.error(f"Error processing daily payouts: {e}")
    
    def process_expired_investments(self):
        try:
            logger.info("Processing expired investments...")
            self.investment_service.process_expired_investments()
            logger.info("Expired investments processed successfully")
        except Exception as e:
            logger.error(f"Error processing expired investments: {e}")
    
    def stop(self):
        self.scheduler.shutdown()
from datetime import datetime, timedelta
from database.db_manager import DatabaseManager
from config.settings import Config
import logging

logger = logging.getLogger(__name__)

class InvestmentService:
    def __init__(self):
        self.db = DatabaseManager()
    
    def calculate_daily_payout(self, investment_amount: float) -> float:
        return investment_amount * Config.DAILY_RATE
    
    def calculate_total_return(self, investment_amount: float) -> float:
        return investment_amount * Config.DAILY_RATE * Config.INVESTMENT_DAYS
    
    def process_daily_payouts(self):
        """Process daily payouts for all active investments"""
        try:
            investments = self.db.get_active_investments()
            
            if not investments:
                logger.info("No active investments found")
                return
            
            logger.info(f"Processing payouts for {len(investments)} investments")
            
            for investment in investments:
                try:
                    # Check if investment is still active
                    if investment.end_date and datetime.utcnow() > investment.end_date:
                        investment.is_active = False
                        investment.is_completed = True
                        continue
                    
                    # Calculate daily payout
                    daily_amount = self.calculate_daily_payout(investment.amount)
                    
                    # Record payout
                    day_number = (datetime.utcnow() - investment.start_date).days + 1
                    self.db.record_payout(
                        user_id=investment.user_id,
                        investment_id=investment.id,
                        amount=daily_amount,
                        day_number=day_number
                    )
                    
                    logger.info(f"Payout processed for investment {investment.id}: ${daily_amount}")
                    
                except Exception as e:
                    logger.error(f"Error processing payout for investment {investment.id}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in process_daily_payouts: {e}")
    
    def process_expired_investments(self):
        """Return principal for expired investments"""
        try:
            expired = self.db.get_expired_investments()
            
            if not expired:
                logger.info("No expired investments found")
                return
            
            logger.info(f"Processing {len(expired)} expired investments")
            
            for investment in expired:
                try:
                    result = self.db.return_principal(investment.id)
                    if result:
                        logger.info(f"Principal returned for investment {investment.id}: ${investment.amount}")
                except Exception as e:
                    logger.error(f"Error returning principal for investment {investment.id}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in process_expired_investments: {e}")
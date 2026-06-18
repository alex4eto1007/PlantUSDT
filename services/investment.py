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
    
    def process_referral_earnings(self, investment):
        """Process referral earnings for the referrer (Level 1)"""
        try:
            user = self.db.get_user_by_id(investment.user_id)
            if not user or not user.referred_by:
                return 0
            
            referrer = self.db.get_user_by_id(user.referred_by)
            if not referrer:
                return 0
            
            daily_payout = self.calculate_daily_payout(investment.amount)
            referral_bonus = daily_payout * 0.05  # 5% of daily earnings
            
            # Credit to referrer
            referrer.balance += referral_bonus
            referrer.total_earned += referral_bonus
            referrer.referral_earnings_all_time += referral_bonus
            referrer.total_earnings_all_time += referral_bonus
            
            investment.referral_earnings_paid += referral_bonus
            
            session = self.db.get_session()
            session.commit()
            
            logger.info(f"Level 1 referral bonus: {referrer.telegram_id} got ${referral_bonus} from {user.telegram_id}")
            
            # ============================================
            # LEVEL 2: Referrer's referrer also gets 5% of this referral bonus
            # ============================================
            if referrer.referred_by:
                level2_referrer = self.db.get_user_by_id(referrer.referred_by)
                if level2_referrer:
                    level2_bonus = referral_bonus * 0.05  # 5% of Level 1 bonus
                    level2_referrer.balance += level2_bonus
                    level2_referrer.total_earned += level2_bonus
                    level2_referrer.referral_earnings_all_time += level2_bonus
                    level2_referrer.total_earnings_all_time += level2_bonus
                    session = self.db.get_session()
                    session.commit()
                    logger.info(f"Level 2 referral bonus: {level2_referrer.telegram_id} got ${level2_bonus} from {user.telegram_id}")
            
            return referral_bonus
        except Exception as e:
            logger.error(f"Error processing referral earnings: {e}")
            return 0
    
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
                    if investment.end_date and datetime.utcnow() > investment.end_date:
                        investment.is_active = False
                        investment.is_completed = True
                        continue
                    
                    daily_amount = self.calculate_daily_payout(investment.amount)
                    day_number = (datetime.utcnow() - investment.start_date).days + 1
                    
                    # Record payout to user
                    self.db.record_payout(
                        user_id=investment.user_id,
                        investment_id=investment.id,
                        amount=daily_amount,
                        day_number=day_number
                    )
                    
                    # ============================================
                    # TRACK INVESTMENT EARNINGS
                    # ============================================
                    user = self.db.get_user_by_id(investment.user_id)
                    if user:
                        user.investment_earnings_all_time = (user.investment_earnings_all_time or 0) + daily_amount
                        user.total_earnings_all_time = (user.total_earnings_all_time or 0) + daily_amount
                        session = self.db.get_session()
                        session.commit()
                    
                    # ============================================
                    # PROCESS REFERRAL EARNINGS (Level 1 and Level 2)
                    # ============================================
                    self.process_referral_earnings(investment)
                    
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

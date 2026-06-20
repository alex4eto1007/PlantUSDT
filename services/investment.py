from datetime import datetime, timedelta
from database.db_manager import DatabaseManager
from database.models import Investment, User, DailyPayout
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
        """Process referral earnings for the referrer (Level 1 and Level 2)"""
        try:
            session = self.db.get_session()
            
            # Get the user who made the investment
            user = session.query(User).filter_by(id=investment.user_id).first()
            if not user or not user.referred_by:
                return 0
            
            # Level 1: Direct referrer
            referrer = session.query(User).filter_by(id=user.referred_by).first()
            if not referrer:
                return 0
            
            daily_payout = self.calculate_daily_payout(investment.amount)
            referral_bonus = daily_payout * 0.05  # 5% of daily earnings
            
            # Credit Level 1 referrer
            referrer.balance += referral_bonus
            referrer.total_earned += referral_bonus
            referrer.referral_earnings_all_time = (referrer.referral_earnings_all_time or 0) + referral_bonus
            referrer.total_earnings_all_time = (referrer.total_earnings_all_time or 0) + referral_bonus
            
            # Track referral earnings paid on the investment
            investment.referral_earnings_paid = (investment.referral_earnings_paid or 0) + referral_bonus
            
            session.commit()
            
            logger.info(f"Level 1 referral bonus: {referrer.telegram_id} got ${referral_bonus:.2f} from {user.telegram_id}")
            
            # ============================================
            # LEVEL 2: Referrer's referrer also gets 5% of this referral bonus
            # ============================================
            if referrer.referred_by:
                level2_referrer = session.query(User).filter_by(id=referrer.referred_by).first()
                if level2_referrer:
                    level2_bonus = referral_bonus * 0.05  # 5% of Level 1 bonus
                    
                    level2_referrer.balance += level2_bonus
                    level2_referrer.total_earned += level2_bonus
                    level2_referrer.referral_earnings_all_time = (level2_referrer.referral_earnings_all_time or 0) + level2_bonus
                    level2_referrer.total_earnings_all_time = (level2_referrer.total_earnings_all_time or 0) + level2_bonus
                    
                    session.commit()
                    logger.info(f"Level 2 referral bonus: {level2_referrer.telegram_id} got ${level2_bonus:.2f} from {user.telegram_id}")
            
            return referral_bonus
            
        except Exception as e:
            logger.error(f"Error processing referral earnings: {e}")
            session.rollback()
            return 0
        finally:
            session.close()
    
    def create_investment(self, user_id: int, field_number: int, amount: float):
        """Create a new investment with 24-hour payout timer"""
        try:
            session = self.db.get_session()
            
            # Check if field is already active
            existing = session.query(Investment).filter_by(
                user_id=user_id, 
                field_number=field_number,
                is_active=True
            ).first()
            if existing:
                return None
            
            from config.settings import Config
            total_return = amount * Config.DAILY_RATE * Config.INVESTMENT_DAYS
            now = datetime.utcnow()
            
            investment = Investment(
                user_id=user_id,
                field_number=field_number,
                amount=amount,
                total_return=total_return,
                end_date=now + timedelta(days=Config.INVESTMENT_DAYS),
                next_payout_date=now + timedelta(hours=24)  # First payout in 24 hours
            )
            session.add(investment)
            
            # Deduct from user balance
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.total_invested += amount
                user.balance -= amount
            
            session.commit()
            logger.info(f"Investment created: Field {field_number}, ${amount}, next payout at {investment.next_payout_date}")
            return investment
            
        except Exception as e:
            logger.error(f"Error creating investment: {e}")
            session.rollback()
            return None
        finally:
            session.close()
    
    def process_daily_payouts(self):
        """Process daily payouts - 24 hours after investment or last payout"""
        try:
            session = self.db.get_session()
            
            # Get all active investments
            investments = session.query(Investment).filter_by(
                is_active=True
            ).all()
            
            if not investments:
                logger.info("No active investments found")
                return
            
            logger.info(f"Processing payouts for {len(investments)} investments")
            now = datetime.utcnow()
            
            for investment in investments:
                try:
                    # Check if investment is expired
                    if investment.end_date and now > investment.end_date:
                        investment.is_active = False
                        investment.is_completed = True
                        session.commit()
                        logger.info(f"Investment {investment.id} expired and marked as completed")
                        continue
                    
                    # ============================================
                    # CHECK IF NEXT PAYOUT IS DUE (24 hours after last payout)
                    # ============================================
                    if investment.next_payout_date and now < investment.next_payout_date:
                        # Not yet time for payout
                        continue
                    
                    # Calculate daily payout
                    daily_amount = self.calculate_daily_payout(investment.amount)
                    day_number = (now - investment.start_date).days + 1
                    
                    # Record payout to user
                    payout = DailyPayout(
                        user_id=investment.user_id,
                        investment_id=investment.id,
                        amount=daily_amount,
                        day_number=day_number
                    )
                    session.add(payout)
                    
                    # Update investment
                    investment.paid_out = (investment.paid_out or 0) + daily_amount
                    investment.last_payout_date = now
                    
                    # ============================================
                    # UPDATE NEXT PAYOUT DATE (24 hours from now)
                    # ============================================
                    investment.next_payout_date = now + timedelta(hours=24)
                    
                    # Credit user's balance
                    user = session.query(User).filter_by(id=investment.user_id).first()
                    if user:
                        user.balance += daily_amount
                        user.total_earned += daily_amount
                        user.investment_earnings_all_time = (user.investment_earnings_all_time or 0) + daily_amount
                        user.total_earnings_all_time = (user.total_earnings_all_time or 0) + daily_amount
                    
                    session.commit()
                    
                    # Process referral earnings (Level 1 and Level 2)
                    self.process_referral_earnings(investment)
                    
                    logger.info(f"Payout processed for investment {investment.id}: ${daily_amount:.2f}, next payout at {investment.next_payout_date}")
                    
                except Exception as e:
                    logger.error(f"Error processing payout for investment {investment.id}: {e}")
                    session.rollback()
                    continue
                    
        except Exception as e:
            logger.error(f"Error in process_daily_payouts: {e}")
        finally:
            session.close()
    
    def process_expired_investments(self):
        """Return principal for expired investments"""
        try:
            session = self.db.get_session()
            
            # Get expired but not completed investments
            expired = session.query(Investment).filter(
                Investment.end_date < datetime.utcnow(),
                Investment.is_active == True,
                Investment.principal_returned == False
            ).all()
            
            if not expired:
                logger.info("No expired investments found")
                return
            
            logger.info(f"Processing {len(expired)} expired investments")
            
            for investment in expired:
                try:
                    # Mark as inactive and completed
                    investment.is_active = False
                    investment.is_completed = True
                    investment.principal_returned = True
                    
                    # Return principal to user's balance
                    user = session.query(User).filter_by(id=investment.user_id).first()
                    if user:
                        user.balance += investment.amount
                    
                    session.commit()
                    logger.info(f"Principal returned for investment {investment.id}: ${investment.amount}")
                    
                except Exception as e:
                    logger.error(f"Error returning principal for investment {investment.id}: {e}")
                    session.rollback()
                    continue
                    
        except Exception as e:
            logger.error(f"Error in process_expired_investments: {e}")
        finally:
            session.close()
    
    def get_investment_status(self, user_id: int):
        """Get investment status for a user"""
        try:
            session = self.db.get_session()
            investments = session.query(Investment).filter_by(
                user_id=user_id
            ).all()
            
            result = []
            for inv in investments:
                result.append({
                    'id': inv.id,
                    'field_number': inv.field_number,
                    'amount': inv.amount,
                    'paid_out': inv.paid_out,
                    'total_return': inv.total_return,
                    'start_date': inv.start_date.isoformat(),
                    'end_date': inv.end_date.isoformat() if inv.end_date else None,
                    'next_payout_date': inv.next_payout_date.isoformat() if inv.next_payout_date else None,
                    'is_active': inv.is_active,
                    'is_completed': inv.is_completed,
                    'principal_returned': inv.principal_returned
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting investment status: {e}")
            return []
        finally:
            session.close()

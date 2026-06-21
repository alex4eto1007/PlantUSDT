from datetime import datetime, timedelta
from database.db_manager import DatabaseManager
from database.models import Investment, User, DailyPayout
from config.settings import Config
import logging
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

class InvestmentService:
    def __init__(self):
        self.db = DatabaseManager()

    def calculate_daily_payout(self, investment_amount: float) -> float:
        return investment_amount * Config.DAILY_RATE

    def calculate_total_return(self, investment_amount: float) -> float:
        return investment_amount * Config.DAILY_RATE * Config.INVESTMENT_DAYS

    async def process_referral_earnings(self, investment):
        """Process referral earnings based on deposits (5% of deposit amount)"""
        try:
            logger.info(f"🔔 REFERRAL DEBUG: process_referral_earnings called for investment {investment.id}")
            session = self.db.get_session()

            # Get the user who made the investment
            user = session.query(User).filter_by(id=investment.user_id).first()
            if not user or not user.referred_by:
                logger.info(f"🔔 REFERRAL DEBUG: User {investment.user_id} has no referrer")
                return 0

            # Get the referrer
            referrer = session.query(User).filter_by(id=user.referred_by).first()
            if not referrer:
                logger.info(f"🔔 REFERRAL DEBUG: Referrer not found for user {investment.user_id}")
                return 0

            # Calculate referral bonus based on deposit (investment amount)
            referral_bonus = investment.amount * 0.05

            # Credit the referrer
            referrer.balance += referral_bonus
            referrer.total_earned += referral_bonus
            referrer.referral_earnings_all_time = (referrer.referral_earnings_all_time or 0) + referral_bonus
            referrer.referral_deposit_earnings = (referrer.referral_deposit_earnings or 0) + referral_bonus
            referrer.total_earnings_all_time = (referrer.total_earnings_all_time or 0) + referral_bonus

            session.commit()
            logger.info(f"Referrer {referrer.telegram_id} earned ${referral_bonus:.2f} from {user.telegram_id}'s deposit of ${investment.amount}")

            # --- SEND TELEGRAM NOTIFICATION VIA API ---
            logger.info(f"🔔 REFERRAL DEBUG: Attempting to send notification to {referrer.telegram_id}")
            try:
                async def send_notification():
                    try:
                        logger.info(f"🔔 REFERRAL DEBUG: Inside send_notification function")
                        bot_token = Config.BOT_TOKEN
                        username = user.username or user.first_name or "User"
                        total_refs = session.query(User).filter_by(referred_by=referrer.id).count()
                        
                        message = (
                            f"🎁 **Referral Bonus Received**\n\n"
                            f"Your referral **@{username}** deposited **${investment.amount:.2f} USDT**\n\n"
                            f"**+${referral_bonus:.2f} USDT** credited to your balance! (5% bonus)\n"
                            f"━━━━━━━━━━━━━━━━━━━━\n"
                            f"💰 Your balance: **${referrer.balance:.2f}**\n"
                            f"👥 Total referrals: **{total_refs}**"
                        )
                        
                        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                        payload = {
                            "chat_id": referrer.telegram_id,
                            "text": message,
                            "parse_mode": "Markdown"
                        }
                        
                        logger.info(f"🔔 REFERRAL DEBUG: Sending to URL: {url[:50]}...")
                        async with aiohttp.ClientSession() as http_session:
                            async with http_session.post(url, json=payload) as response:
                                logger.info(f"🔔 REFERRAL DEBUG: Response status: {response.status}")
                                if response.status == 200:
                                    logger.info(f"✅ Referral notification sent to {referrer.telegram_id}")
                                else:
                                    response_text = await response.text()
                                    logger.error(f"❌ API returned {response.status}: {response_text}")
                    except Exception as e:
                        logger.error(f"❌ Error sending notification: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                
                logger.info(f"🔔 REFERRAL DEBUG: Creating task for send_notification")
                asyncio.create_task(send_notification())
                logger.info(f"🔔 REFERRAL DEBUG: Task created successfully")
            except Exception as e:
                logger.error(f"❌ Error in notification setup: {e}")
                import traceback
                logger.error(traceback.format_exc())
            # --- END NOTIFICATION ---

            return referral_bonus

        except Exception as e:
            logger.error(f"Error processing referral earnings: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
                next_payout_date=now + timedelta(hours=24)
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

    async def process_daily_payouts(self):
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

                    # Check if next payout is due
                    if investment.next_payout_date and now < investment.next_payout_date:
                        continue

                    # Calculate daily payout
                    daily_amount = self.calculate_daily_payout(investment.amount)
                    day_number = (now - investment.start_date).days + 1

                    # Record payout
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
                    investment.next_payout_date = now + timedelta(hours=24)

                    # Credit user's balance
                    user = session.query(User).filter_by(id=investment.user_id).first()
                    if user:
                        user.balance += daily_amount
                        user.total_earned += daily_amount
                        user.investment_earnings_all_time = (user.investment_earnings_all_time or 0) + daily_amount
                        user.total_earnings_all_time = (user.total_earnings_all_time or 0) + daily_amount

                    session.commit()

                    # Process referral earnings
                    await self.process_referral_earnings(investment)

                    logger.info(f"Payout processed for investment {investment.id}: ${daily_amount:.2f}")

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
                    investment.is_active = False
                    investment.is_completed = True
                    investment.principal_returned = True

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

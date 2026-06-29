from datetime import datetime, timedelta
from database.db_manager import DatabaseManager
from database.models import Investment, User, DailyPayout
from config.settings import Config
from services.notifications import NotificationService
import logging
import requests

logger = logging.getLogger(__name__)

class InvestmentService:
    def __init__(self):
        self.db = DatabaseManager()
        self.notification_service = NotificationService()
        # Updated multipliers: 1 day 2%, 7 days 18%, 30 days 80%
        self.lock_multipliers = {
            1: 1.02,    # 2% return
            7: 1.18,    # 18% return
            30: 1.80    # 80% return
        }

    def calculate_return(self, amount: float, lock_period: int) -> float:
        """Calculate the total return based on lock period"""
        multiplier = self.lock_multipliers.get(lock_period, 1.80)
        return round(amount * multiplier, 2)

    async def process_referral_earnings(self, investment):
        """Process referral earnings based on deposits (1% of deposit amount)"""
        logger.info("🔔🔔🔔 REFERRAL FUNCTION STARTED 🔔🔔🔔")
        try:
            session = self.db.get_session()

            user = session.query(User).filter_by(id=investment.user_id).first()
            if not user or not user.referred_by:
                logger.info(f"🔔 REFERRAL DEBUG: User {investment.user_id} has no referrer")
                return 0

            referrer = session.query(User).filter_by(id=user.referred_by).first()
            if not referrer:
                logger.info(f"🔔 REFERRAL DEBUG: Referrer not found for user {investment.user_id}")
                return 0

            referral_bonus = investment.amount * 0.01  # 1% instead of 5%

            referrer.balance += referral_bonus
            referrer.total_earned += referral_bonus
            referrer.referral_earnings_all_time = (referrer.referral_earnings_all_time or 0) + referral_bonus
            referrer.referral_deposit_earnings = (referrer.referral_deposit_earnings or 0) + referral_bonus
            referrer.total_earnings_all_time = (referrer.total_earnings_all_time or 0) + referral_bonus

            session.commit()
            logger.info(f"Referrer {referrer.telegram_id} earned ${referral_bonus:.2f} from {user.telegram_id}'s deposit of ${investment.amount} on Polygon")

            # --- SEND REFERRAL NOTIFICATION ---
            try:
                await self.notification_service.send_referral_notification(
                    referrer_id=referrer.telegram_id,
                    amount=referral_bonus,
                    referred_user=user
                )
            except Exception as e:
                logger.error(f"Error sending referral notification: {e}")

            # --- SEND TELEGRAM NOTIFICATION VIA API (Legacy backup) ---
            logger.info("🔔🔔🔔 ENTERING NOTIFICATION SECTION 🔔🔔🔔")
            try:
                logger.info(f"🔔 REFERRAL DEBUG: Attempting to send notification to {referrer.telegram_id}")
                
                bot_token = Config.BOT_TOKEN
                username = user.username or user.first_name or "User"
                total_refs = session.query(User).filter_by(referred_by=referrer.id).count()
                
                message = (
                    f"🎁 **Referral Bonus Received (Polygon)**\n\n"
                    f"Your referral **@{username}** deposited **${investment.amount:.2f} USDT**\n\n"
                    f"**+${referral_bonus:.2f} USDT** credited to your balance! (1% bonus)\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 Your balance: **${referrer.balance:.2f}**\n"
                    f"👥 Total referrals: **{total_refs}**\n"
                    f"⛓️ Network: **Polygon**"
                )
                
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": referrer.telegram_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                
                logger.info(f"🔔 REFERRAL DEBUG: Sending to URL: {url[:50]}...")
                response = requests.post(url, json=payload, timeout=10)
                logger.info(f"🔔 REFERRAL DEBUG: Response status: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info(f"✅ Referral notification sent to {referrer.telegram_id}")
                else:
                    logger.error(f"❌ API returned {response.status_code}: {response.text}")
                    
            except Exception as e:
                logger.error(f"❌ Error sending notification: {e}")
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

    def create_investment(self, user_id: int, field_number: int, amount: float, lock_period: int):
        """Create a new locked investment on Polygon"""
        try:
            session = self.db.get_session()

            existing = session.query(Investment).filter_by(
                user_id=user_id,
                field_number=field_number,
                is_active=True
            ).first()
            if existing:
                return None, "Field is already active"

            user = session.query(User).filter_by(id=user_id).first()
            if not user or user.balance < amount:
                return None, "Insufficient balance"

            expected_return = self.calculate_return(amount, lock_period)
            now = datetime.utcnow()
            unlock_date = now + timedelta(days=lock_period)

            investment = Investment(
                user_id=user_id,
                field_number=field_number,
                amount=amount,
                lock_period=lock_period,
                unlock_date=unlock_date,
                expected_return=expected_return,
                start_date=now,
                end_date=unlock_date,
                is_active=True,
                is_locked=True
            )
            session.add(investment)

            user.balance -= amount
            user.total_invested += amount

            session.commit()
            logger.info(f"Investment created on Polygon: Field {field_number}, ${amount}, {lock_period} days, returns ${expected_return}")
            return investment, None

        except Exception as e:
            logger.error(f"Error creating investment: {e}")
            session.rollback()
            return None, str(e)
        finally:
            session.close()

    async def process_locked_investments(self):
        """Process investments that have reached their unlock date on Polygon"""
        try:
            session = self.db.get_session()
            now = datetime.utcnow()

            unlocked = session.query(Investment).filter(
                Investment.is_active == True,
                Investment.is_locked == True,
                Investment.unlock_date <= now
            ).all()

            if not unlocked:
                logger.info("No locked investments to process on Polygon")
                return

            logger.info(f"🔓 Processing {len(unlocked)} unlocked investments on Polygon")

            for investment in unlocked:
                try:
                    # Get the user FIRST and attach to session
                    user = session.query(User).filter_by(id=investment.user_id).first()
                    if not user:
                        logger.error(f"User {investment.user_id} not found")
                        continue

                    # Mark investment as unlocked
                    investment.is_locked = False
                    investment.is_active = False
                    investment.is_completed = True
                    investment.completed_at = now
                    investment.principal_returned = True

                    # Update the user's balance
                    user.balance += investment.expected_return
                    user.total_earned += investment.expected_return
                    user.investment_earnings_all_time = (user.investment_earnings_all_time or 0) + investment.expected_return
                    user.total_earnings_all_time = (user.total_earnings_all_time or 0) + investment.expected_return

                    # Create a DailyPayout record for the profit (so it appears in history)
                    profit = investment.expected_return - investment.amount
                    payout = DailyPayout(
                        user_id=user.id,
                        investment_id=investment.id,
                        amount=profit,
                        day_number=investment.lock_period,
                        paid_at=now
                    )
                    session.add(payout)

                    # COMMIT - this saves both the investment AND user changes
                    session.commit()
                    logger.info(f"✅ User {user.telegram_id} balance updated: +${investment.expected_return:.2f} (Field {investment.field_number})")

                    # Send unlock notification
                    try:
                        await self.notification_service.send_unlock_notification(
                            user_id=user.telegram_id,
                            field_number=investment.field_number,
                            amount=investment.amount,
                            profit=profit,
                            lock_period=investment.lock_period
                        )
                    except Exception as e:
                        logger.error(f"Error sending unlock notification: {e}")

                    # Process referral earnings
                    await self.process_referral_earnings(investment)

                    # Send Telegram message
                    try:
                        from bot.main import application
                        if application and application.bot:
                            profit = investment.expected_return - investment.amount
                            message = (
                                f"🎉 **Investment Completed!**\n\n"
                                f"Your investment in **Field #{investment.field_number}** has been completed!\n\n"
                                f"💰 Amount invested: **${investment.amount:.2f}**\n"
                                f"📈 Profit: **+${profit:.2f}**\n"
                                f"💵 Total received: **${investment.expected_return:.2f}**\n"
                                f"📅 Lock period: **{investment.lock_period} days**\n"
                                f"⛓️ Network: **Polygon**\n\n"
                                f"🌱 Your balance: **${user.balance:.2f}**"
                            )
                            await application.bot.send_message(
                                chat_id=user.telegram_id,
                                text=message,
                                parse_mode='Markdown'
                            )
                            logger.info(f"✅ Completion notification sent to {user.telegram_id}")
                    except Exception as e:
                        logger.error(f"Error sending completion notification: {e}")

                except Exception as e:
                    logger.error(f"Error processing investment {investment.id}: {e}")
                    session.rollback()
                    continue

        except Exception as e:
            logger.error(f"Error in process_locked_investments: {e}")
        finally:
            session.close()

    def get_available_lock_periods(self):
        """Get available lock periods with their returns"""
        return [
            {'days': 1, 'return_percent': 2, 'multiplier': 1.02},
            {'days': 7, 'return_percent': 18, 'multiplier': 1.18},
            {'days': 30, 'return_percent': 80, 'multiplier': 1.80}
        ]

    def get_investment_status(self, user_id: int):
        """Get investment status for a user on Polygon"""
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
                    'lock_period': inv.lock_period,
                    'expected_return': inv.expected_return,
                    'unlock_date': inv.unlock_date.isoformat() if inv.unlock_date else None,
                    'start_date': inv.start_date.isoformat(),
                    'is_active': inv.is_active,
                    'is_locked': inv.is_locked,
                    'is_completed': inv.is_completed,
                    'network': 'Polygon'
                })

            return result

        except Exception as e:
            logger.error(f"Error getting investment status: {e}")
            return []
        finally:
            session.close()

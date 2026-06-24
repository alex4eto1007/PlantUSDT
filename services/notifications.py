import logging
from telegram import Bot
from config.settings import Config

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.bot = Bot(token=Config.BOT_TOKEN)
    
    async def send_deposit_notification(self, user_id: int, amount: float, tx_hash: str):
        """Send notification when a deposit is detected"""
        try:
            message = (
                f"💰 **Deposit Received on Polygon!**\n\n"
                f"Amount: **${amount:.2f} USDT**\n"
                f"Network: **Polygon** ⛓️\n"
                f"TX: `{tx_hash[:10]}...{tx_hash[-8:]}`\n\n"
                f"Your balance has been updated! 🌱\n"
                f"💵 New balance: Check the app!"
            )
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Deposit notification sent to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send deposit notification: {e}")
    
    async def send_unlock_notification(self, user_id: int, field_number: int, amount: float, profit: float, lock_period: int):
        """Send notification when an investment unlocks"""
        try:
            total_return = amount + profit
            message = (
                f"🎉 **Field #{field_number} Unlocked!**\n\n"
                f"Your {lock_period}-day investment is complete!\n"
                f"💰 Amount invested: **${amount:.2f}**\n"
                f"📈 Profit earned: **+${profit:.2f}**\n"
                f"💵 Total received: **${total_return:.2f}**\n\n"
                f"Your funds are now in your balance! 🌱"
            )
            await self.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Unlock notification sent to user {user_id} for Field #{field_number}")
        except Exception as e:
            logger.error(f"Failed to send unlock notification: {e}")
    
    async def send_referral_notification(self, referrer_id: int, amount: float, referred_user):
        """Send notification when a referral deposits (with username fallback)"""
        try:
            # Handle username fallback
            if referred_user:
                if hasattr(referred_user, 'username') and referred_user.username:
                    name = f"@{referred_user.username}"
                elif hasattr(referred_user, 'first_name') and referred_user.first_name:
                    name = referred_user.first_name
                else:
                    name = "a friend"
            else:
                name = "a friend"
            
            message = (
                f"🎁 **Referral Bonus Earned!**\n\n"
                f"Your referral **{name}** made a deposit!\n"
                f"You earned **${amount:.2f} USDT** (5% bonus)\n"
                f"💰 This has been added to your balance!\n\n"
                f"Keep sharing your referral link to earn more! 👥"
            )
            await self.bot.send_message(
                chat_id=referrer_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"✅ Referral notification sent to referrer {referrer_id}")
        except Exception as e:
            logger.error(f"Failed to send referral notification: {e}")

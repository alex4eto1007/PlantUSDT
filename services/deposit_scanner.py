from services.wallet import WalletService
from database.db_manager import DatabaseManager
from datetime import datetime, timedelta
import logging
import asyncio

logger = logging.getLogger(__name__)

class DepositScanner:
    def __init__(self):
        self.wallet_service = WalletService()
        self.db = DatabaseManager()
        self.last_checked_block = None
    
    async def scan_for_deposits(self, bot=None):
        """Scan for new deposits and process them"""
        try:
            logger.info("Scanning for new deposits...")
            
            users = self.db.get_all_users()
            users_with_wallets = [u for u in users if u.wallet_address]
            
            if not users_with_wallets:
                logger.info("No users with wallet addresses found")
                return
            
            for user in users_with_wallets:
                try:
                    # Check every 5 minutes
                    if user.last_deposit_check and (datetime.utcnow() - user.last_deposit_check) < timedelta(minutes=5):
                        continue
                    
                    # Check for deposits
                    deposits = self.wallet_service.check_user_deposits(
                        user.wallet_address,
                        hours_back=1
                    )
                    
                    if deposits:
                        for deposit in deposits:
                            # Process deposit
                            processed = self.db.process_deposit(
                                user_id=user.id,
                                amount=deposit['amount'],
                                tx_hash=deposit['tx_hash'],
                                from_address=deposit['from'],
                                block_number=0
                            )
                            
                            if processed:
                                logger.info(f"Deposit processed for user {user.telegram_id}: {deposit['amount']} USDT")
                                
                                # Send notification to user
                                if bot:
                                    await self.notify_user(bot, user, deposit)
                    
                    # Update last check time
                    self.db.update_last_deposit_check(user.id)
                    
                except Exception as e:
                    logger.error(f"Error checking deposits for user {user.telegram_id}: {e}")
                    continue
            
            logger.info("Deposit scan completed")
            
        except Exception as e:
            logger.error(f"Error in deposit scanner: {e}")
    
    async def notify_user(self, bot, user, deposit):
        """Send notification to user about successful deposit"""
        try:
            message = f"""✅ **Deposit Confirmed!**

💰 **Amount:** ${deposit['amount']:.2f} USDT
🔗 **Transaction:** `{deposit['tx_hash'][:10]}...{deposit['tx_hash'][-8:]}`
📅 **Time:** {deposit['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} UTC

🌱 Your balance has been updated!
You can now invest in any of the 3 planting fields.

Use the Mini App to start investing! 🚀"""
            
            await bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Notification sent to user {user.telegram_id}")
            
        except Exception as e:
            logger.error(f"Error sending notification to user {user.telegram_id}: {e}")
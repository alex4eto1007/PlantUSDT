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
    
    async def scan_for_deposits(self):
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
                    if user.last_deposit_check and (datetime.utcnow() - user.last_deposit_check) < timedelta(minutes=10):
                        continue
                    
                    result = self.wallet_service.check_for_deposits(
                        user.wallet_address,
                        amount=1,
                        hours_back=1
                    )
                    
                    if result.get('success'):
                        deposits = result.get('deposits', [])
                        for deposit in deposits:
                            processed = self.db.process_deposit(
                                user_id=user.id,
                                amount=deposit['amount'],
                                tx_hash=deposit['tx_hash'],
                                from_address=deposit['from'],
                                block_number=0
                            )
                            if processed:
                                logger.info(f"Deposit processed for user {user.telegram_id}: {deposit['amount']} USDT")
                    
                    self.db.update_last_deposit_check(user.id)
                    
                except Exception as e:
                    logger.error(f"Error checking deposits for user {user.telegram_id}: {e}")
                    continue
            
            logger.info("Deposit scan completed")
            
        except Exception as e:
            logger.error(f"Error in deposit scanner: {e}")
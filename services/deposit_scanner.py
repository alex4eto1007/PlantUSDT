import aiohttp
import asyncio
from datetime import datetime, timedelta
from database.db_manager import DatabaseManager
from database.models import User, Deposit
from config.settings import Config
import logging

logger = logging.getLogger(__name__)

class DepositScanner:
    def __init__(self):
        self.db = DatabaseManager()
        self.api_key = Config.BSC_SCAN_API_KEY
        self.project_wallet = Config.WALLET_ADDRESS.lower()
        self.scan_interval = 300  # 5 minutes
        self.confirmations = 6  # BSC block confirmations

    async def scan_for_deposits(self, bot):
        """Scan for new deposits on BSC"""
        try:
            logger.info("Scanning for new deposits...")
            session = self.db.get_session()

            # Get all users with wallet addresses
            users = session.query(User).filter(
                User.wallet_address.isnot(None),
                User.wallet_address != ''
            ).all()

            if not users:
                logger.info("No users with wallets found")
                return

            # Get current block number
            current_block = await self._get_current_block()
            if not current_block:
                logger.error("Failed to get current block number")
                return

            # Check each user's wallet for deposits
            for user in users:
                try:
                    user_wallet = user.wallet_address.lower()
                    
                    # Check if the user has a new USDT balance
                    usdt_balance = await self._get_usdt_balance(user_wallet)
                    logger.info(f"📊 User {user.telegram_id} USDT balance: ${usdt_balance:.2f}")

                except Exception as e:
                    logger.error(f"Error processing user {user.telegram_id}: {e}")
                    continue

            session.close()

        except Exception as e:
            logger.error(f"Error in deposit scanner: {e}")

    async def check_deposit_with_amount(self, user_id: int, expected_amount: float, bot):
        """Check for a deposit with a specific expected amount using BSC RPC"""
        try:
            logger.info(f"🔍 Checking deposit for user {user_id}, expected: ${expected_amount:.2f}")
            
            session = self.db.get_session()

            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                logger.error(f"❌ User {user_id} not found")
                return {'success': False, 'message': 'User not found'}
            
            if not user.wallet_address:
                logger.error(f"❌ User {user_id} has no wallet connected")
                return {'success': False, 'message': 'No wallet connected'}

            user_wallet = user.wallet_address.lower()
            logger.info(f"🔍 User wallet: {user_wallet}")
            
            # Check if we already processed a deposit for this user with this amount
            existing = session.query(Deposit).filter_by(
                user_id=user.id,
                amount=expected_amount
            ).first()
            
            if existing:
                logger.info(f"✅ Deposit of ${expected_amount:.2f} already processed")
                return {'success': True, 'message': 'Deposit already processed'}
            
            # Check the USDT balance of the PROJECT WALLET
            project_balance = await self._get_usdt_balance(self.project_wallet)
            logger.info(f"📊 Project wallet USDT balance: ${project_balance:.2f}")
            
            # Check if the project wallet has received the expected amount
            if project_balance >= expected_amount:
                # Process deposit
                deposit = Deposit(
                    user_id=user.id,
                    amount=expected_amount,
                    tx_hash=f"0xmanual_{datetime.utcnow().timestamp()}",
                    from_address=user_wallet,
                    block_number=0,
                    confirmed_at=datetime.utcnow(),
                    processed=True
                )
                session.add(deposit)

                user.balance += expected_amount
                user.total_deposited += expected_amount

                session.commit()

                logger.info(f"✅ Deposit detected for user {user_id}: ${expected_amount:.2f}")

                if bot:
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=f"✅ **Deposit Detected!**\n\n"
                                 f"💰 Amount: **${expected_amount:.2f} USDT**\n"
                                 f"📊 Your balance: **${user.balance:.2f}**\n\n"
                                 f"🌱 You can now invest in planting fields!",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Error sending deposit notification: {e}")

                session.close()
                return {'success': True, 'message': 'Deposit detected and processed'}
            else:
                return {'success': False, 'message': f'No deposit of ${expected_amount:.2f} found. Project balance: ${project_balance:.2f}'}

        except Exception as e:
            logger.error(f"Error checking deposit with amount: {e}")
            import traceback
            logger.error(traceback.format_exc())
            session.rollback()
            return {'success': False, 'message': str(e)}

    async def _get_usdt_balance(self, wallet_address: str) -> float:
        """Get USDT balance for a wallet using BSC RPC"""
        try:
            # USDT contract address
            usdt_contract = Config.USDT_CONTRACT
            
            # ERC-20 balanceOf function signature
            # balanceOf(address) = 0x70a08231
            data = f"0x70a08231000000000000000000000000{wallet_address[2:].lower()}"
            
            url = Config.BSC_RPC_URL
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [
                    {
                        "to": usdt_contract,
                        "data": data
                    },
                    "latest"
                ],
                "id": 1
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and data.get('result'):
                            # Convert hex to decimal
                            balance_hex = data.get('result')
                            balance = int(balance_hex, 16)
                            result = balance / 10**18
                            logger.info(f"✅ USDT balance: ${result:.2f}")
                            return result
                        else:
                            logger.warning(f"⚠️ No result in response: {data}")
                            return 0
                    else:
                        logger.error(f"❌ HTTP Error: {response.status}")
                        return 0
        except Exception as e:
            logger.error(f"❌ Error getting USDT balance: {e}")
            return 0

    async def _get_current_block(self):
        """Get the current BSC block number using BSC RPC"""
        try:
            url = Config.BSC_RPC_URL
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    data = await response.json()
                    if data and data.get('result'):
                        return int(data.get('result', '0'), 16)
                    return None
        except Exception as e:
            logger.error(f"Error getting current block: {e}")
            return None

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
                    
                    transactions = await self._get_user_transactions(
                        user_wallet,
                        current_block
                    )

                    for tx in transactions:
                        existing = session.query(Deposit).filter_by(
                            tx_hash=tx['hash']
                        ).first()
                        if existing:
                            continue

                        sender = tx.get('from', '').lower()
                        amount = float(tx.get('value', 0)) / 10**18

                        if sender == user_wallet:
                            logger.info(f"✅ Deposit detected for user {user.telegram_id}: ${amount}")

                            deposit = Deposit(
                                user_id=user.id,
                                amount=amount,
                                tx_hash=tx['hash'],
                                from_address=sender,
                                block_number=tx['block_number'],
                                confirmed_at=datetime.utcnow(),
                                processed=True
                            )
                            session.add(deposit)

                            user.balance += amount
                            user.total_deposited += amount
                            user.total_earnings_all_time = (user.total_earnings_all_time or 0)

                            session.commit()

                            try:
                                await bot.send_message(
                                    chat_id=user.telegram_id,
                                    text=f"✅ **Deposit Detected!**\n\n"
                                         f"💰 Amount: **${amount:.2f} USDT**\n"
                                         f"📊 Your balance: **${user.balance:.2f}**\n\n"
                                         f"🌱 You can now invest in planting fields!",
                                    parse_mode='Markdown'
                                )
                                logger.info(f"✅ Deposit notification sent to {user.telegram_id}")
                            except Exception as e:
                                logger.error(f"Error sending deposit notification: {e}")

                except Exception as e:
                    logger.error(f"Error processing user {user.telegram_id}: {e}")
                    continue

            session.close()

        except Exception as e:
            logger.error(f"Error in deposit scanner: {e}")

    async def check_deposit_with_amount(self, user_id: int, expected_amount: float, bot):
        """Check for a deposit with a specific expected amount."""
        try:
            session = self.db.get_session()

            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user or not user.wallet_address:
                return {'success': False, 'message': 'No wallet connected'}

            user_wallet = user.wallet_address.lower()

            current_block = await self._get_current_block()
            if not current_block:
                return {'success': False, 'message': 'Could not fetch blockchain data'}

            transactions = await self._get_user_transactions_with_amount(
                user_wallet,
                expected_amount,
                current_block
            )

            if not transactions:
                return {'success': False, 'message': 'No deposit found'}

            tx = transactions[0]
            sender = tx.get('from', '').lower()
            amount = float(tx.get('value', 0)) / 10**18

            if abs(amount - expected_amount) > 0.01:
                return {'success': False, 'message': f'Amount mismatch: expected ${expected_amount:.2f}, found ${amount:.2f}'}

            existing = session.query(Deposit).filter_by(tx_hash=tx['hash']).first()
            if existing:
                return {'success': True, 'message': 'Deposit already processed'}

            deposit = Deposit(
                user_id=user.id,
                amount=amount,
                tx_hash=tx['hash'],
                from_address=sender,
                block_number=tx['block_number'],
                confirmed_at=datetime.utcnow(),
                processed=True
            )
            session.add(deposit)

            user.balance += amount
            user.total_deposited += amount

            session.commit()

            logger.info(f"✅ Deposit detected for user {user_id}: ${amount} (expected: ${expected_amount})")

            if bot:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"✅ **Deposit Detected!**\n\n"
                             f"💰 Amount: **${amount:.2f} USDT**\n"
                             f"📊 Your balance: **${user.balance:.2f}**\n\n"
                             f"🌱 You can now invest in planting fields!",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Error sending deposit notification: {e}")

            session.close()
            return {'success': True, 'message': 'Deposit detected and processed'}

        except Exception as e:
            logger.error(f"Error checking deposit with amount: {e}")
            return {'success': False, 'message': str(e)}

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

    async def _get_user_transactions(self, user_wallet: str, current_block: int):
        """Get transactions from a user's wallet to the project wallet using Etherscan V2 API"""
        try:
            start_block = current_block - 5000
            if start_block < 0:
                start_block = 0

            # Etherscan V2 API format with chainid
            url = (
                f"{Config.BSC_SCAN_API}"
                f"?chainid={Config.BSC_SCAN_CHAIN_ID}"
                f"&module=account"
                f"&action=tokentx"
                f"&contractaddress={Config.USDT_CONTRACT}"
                f"&address={user_wallet}"
                f"&startblock={start_block}"
                f"&endblock={current_block}"
                f"&sort=desc"
                f"&apikey={self.api_key}"
            )

            logger.info(f"🔍 FULL URL: {url}")
            logger.info(f"🔍 Checking Etherscan V2: {url[:100]}...")

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"🔍 API Response: {data}")
                        if data.get('status') == '1':
                            transactions = data.get('result', [])
                            filtered = [
                                {
                                    'hash': tx.get('hash'),
                                    'from': tx.get('from'),
                                    'to': tx.get('to'),
                                    'value': int(tx.get('value', 0)),
                                    'block_number': int(tx.get('blockNumber', 0)),
                                }
                                for tx in transactions
                                if tx.get('to', '').lower() == self.project_wallet
                            ]
                            logger.info(f"✅ Found {len(filtered)} USDT transactions to project wallet")
                            return filtered
                        else:
                            logger.warning(f"Etherscan returned: {data}")
                            return []
                    else:
                        logger.error(f"Etherscan returned status: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error getting user transactions: {e}")
            return []

    async def _get_user_transactions_with_amount(self, user_wallet: str, expected_amount: float, current_block: int):
        """Get transactions from a user's wallet with a specific amount using Etherscan V2 API"""
        try:
            start_block = current_block - 5000
            if start_block < 0:
                start_block = 0

            # Etherscan V2 API format with chainid
            url = (
                f"{Config.BSC_SCAN_API}"
                f"?chainid={Config.BSC_SCAN_CHAIN_ID}"
                f"&module=account"
                f"&action=tokentx"
                f"&contractaddress={Config.USDT_CONTRACT}"
                f"&address={user_wallet}"
                f"&startblock={start_block}"
                f"&endblock={current_block}"
                f"&sort=desc"
                f"&apikey={self.api_key}"
            )

            logger.info(f"🔍 Checking Etherscan V2 for amount: {url[:100]}...")

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == '1':
                            transactions = data.get('result', [])
                            expected_amount_wei = int(expected_amount * 10**18)
                            filtered = [
                                {
                                    'hash': tx.get('hash'),
                                    'from': tx.get('from'),
                                    'to': tx.get('to'),
                                    'value': int(tx.get('value', 0)),
                                    'block_number': int(tx.get('blockNumber', 0)),
                                }
                                for tx in transactions
                                if (
                                    tx.get('to', '').lower() == self.project_wallet and
                                    abs(int(tx.get('value', 0)) - expected_amount_wei) < 10**15
                                )
                            ]
                            if filtered:
                                logger.info(f"✅ Found {len(filtered)} matching transactions")
                            return filtered
                        else:
                            logger.warning(f"Etherscan returned: {data}")
                            return []
                    else:
                        logger.error(f"Etherscan returned status: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error getting user transactions with amount: {e}")
            return []

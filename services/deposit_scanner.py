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
                    # Get the user's wallet address
                    user_wallet = user.wallet_address.lower()
                    
                    # Check for new transactions from user wallet to project wallet
                    transactions = await self._get_user_transactions(
                        user_wallet,
                        current_block
                    )

                    for tx in transactions:
                        # Check if this transaction was already processed
                        existing = session.query(Deposit).filter_by(
                            tx_hash=tx['hash']
                        ).first()
                        if existing:
                            continue

                        # 🔑 KEY CHECK: Does the sender match the user's connected wallet?
                        sender = tx.get('from', '').lower()
                        amount = float(tx.get('value', 0)) / 10**18

                        if sender == user_wallet:
                            # ✅ This is THEIR deposit!
                            logger.info(f"✅ Deposit detected for user {user.telegram_id}: ${amount}")

                            # Process the deposit
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

                            # Credit user's balance
                            user.balance += amount
                            user.total_deposited += amount
                            user.total_earnings_all_time = (user.total_earnings_all_time or 0)

                            session.commit()

                            # Send notification to user
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

                        else:
                            # ❌ Not their deposit - ignore
                            logger.info(f"❌ Transaction from {sender} does not match {user_wallet}")

                except Exception as e:
                    logger.error(f"Error processing user {user.telegram_id}: {e}")
                    continue

            session.close()

        except Exception as e:
            logger.error(f"Error in deposit scanner: {e}")

    async def check_deposit_with_amount(self, user_id: int, expected_amount: float, bot):
        """
        Check for a deposit with a specific expected amount.
        This is faster and more accurate than scanning all transactions.
        """
        try:
            session = self.db.get_session()

            # Get the user
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user or not user.wallet_address:
                return {'success': False, 'message': 'No wallet connected'}

            user_wallet = user.wallet_address.lower()

            # Get current block number
            current_block = await self._get_current_block()
            if not current_block:
                return {'success': False, 'message': 'Could not fetch blockchain data'}

            # Check for transactions from user's wallet to project wallet
            transactions = await self._get_user_transactions_with_amount(
                user_wallet,
                expected_amount,
                current_block
            )

            if not transactions:
                return {'success': False, 'message': 'No deposit found'}

            # Process the first matching transaction
            tx = transactions[0]
            sender = tx.get('from', '').lower()
            amount = float(tx.get('value', 0)) / 10**18

            # Verify amount matches (with small tolerance)
            if abs(amount - expected_amount) > 0.01:
                return {'success': False, 'message': f'Amount mismatch: expected ${expected_amount:.2f}, found ${amount:.2f}'}

            # Check if already processed
            existing = session.query(Deposit).filter_by(tx_hash=tx['hash']).first()
            if existing:
                return {'success': True, 'message': 'Deposit already processed'}

            # Process deposit
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

            # Credit user's balance
            user.balance += amount
            user.total_deposited += amount

            session.commit()

            logger.info(f"✅ Deposit detected for user {user_id}: ${amount} (expected: ${expected_amount})")

            # Send notification
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
        """Get transactions from a user's wallet to the project wallet"""
        try:
            # Check the last 5000 blocks (increased from 1000 to catch more transactions)
            start_block = current_block - 5000
            if start_block < 0:
                start_block = 0

            # Get all USDT transactions FROM the user's wallet
            url = (
                f"{Config.BSC_SCAN_API}?"
                f"module=account&action=tokentx"
                f"&contractaddress={Config.USDT_CONTRACT}"
                f"&address={user_wallet}"
                f"&startblock={start_block}"
                f"&endblock={current_block}"
                f"&sort=desc"
                f"&apikey={self.api_key}"
            )

            logger.info(f"🔍 Checking BSCScan for USDT transactions from {user_wallet[:10]}...")

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()
                    if data.get('status') == '1':
                        transactions = data.get('result', [])
                        # Filter: only transactions TO the project wallet
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
                        logger.warning(f"BSCScan returned status: {data.get('status')}, message: {data.get('message')}")
                        return []
        except Exception as e:
            logger.error(f"Error getting user transactions: {e}")
            return []

    async def _get_user_transactions_with_amount(self, user_wallet: str, expected_amount: float, current_block: int):
        """Get transactions from a user's wallet with a specific amount"""
        try:
            # Check the last 5000 blocks (increased from 1000)
            start_block = current_block - 5000
            if start_block < 0:
                start_block = 0

            # Get all USDT transactions FROM the user's wallet
            url = (
                f"{Config.BSC_SCAN_API}?"
                f"module=account&action=tokentx"
                f"&contractaddress={Config.USDT_CONTRACT}"
                f"&address={user_wallet}"
                f"&startblock={start_block}"
                f"&endblock={current_block}"
                f"&sort=desc"
                f"&apikey={self.api_key}"
            )

            logger.info(f"🔍 Checking BSCScan for USDT transactions from {user_wallet[:10]}...")

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    data = await response.json()
                    if data.get('status') == '1':
                        transactions = data.get('result', [])
                        # Filter: only transactions TO the project wallet with matching amount
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
                        logger.warning(f"BSCScan returned status: {data.get('status')}, message: {data.get('message')}")
                        return []
        except Exception as e:
            logger.error(f"Error getting user transactions with amount: {e}")
            return []

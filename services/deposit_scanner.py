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
        self.usdt_contract = Config.USDT_CONTRACT
        self.scan_interval = 300  # 5 minutes

    async def scan_for_deposits(self, bot):
        """Scan for new deposits using BSCScan API to get transaction hashes"""
        try:
            logger.info("🔍 Scanning for new deposits...")
            session = self.db.get_session()

            # Get all users with wallet addresses
            users = session.query(User).filter(
                User.wallet_address.isnot(None),
                User.wallet_address != ''
            ).all()

            if not users:
                logger.info("No users with wallets found")
                session.close()
                return

            # Get the last 50 token transfers to the project wallet
            transfers = await self._get_recent_usdt_transfers()
            if not transfers:
                logger.warning("No recent USDT transfers found")
                session.close()
                return

            # For each user, check if any transfer matches their wallet
            for user in users:
                try:
                    user_wallet = user.wallet_address.lower()
                    
                    # Find transfers from this user to the project wallet
                    matching = [
                        tx for tx in transfers
                        if tx['from'].lower() == user_wallet
                    ]
                    
                    for tx in matching:
                        # Check if this transaction is already processed
                        existing = session.query(Deposit).filter_by(
                            tx_hash=tx['hash']
                        ).first()
                        if existing:
                            continue
                        
                        # Process new deposit
                        amount = float(tx['value']) / 10**18
                        deposit = Deposit(
                            user_id=user.id,
                            amount=amount,
                            tx_hash=tx['hash'],
                            from_address=tx['from'],
                            block_number=tx['block_number'],
                            confirmed_at=datetime.utcnow(),
                            processed=True
                        )
                        session.add(deposit)
                        
                        # Update user balance
                        user.balance += amount
                        user.total_deposited += amount
                        
                        session.commit()
                        
                        logger.info(f"✅ New deposit detected for user {user.telegram_id}: ${amount:.2f} (tx: {tx['hash'][:10]}...)")
                        
                        if bot:
                            try:
                                await bot.send_message(
                                    chat_id=user.telegram_id,
                                    text=f"✅ **Deposit Detected!**\n\n"
                                         f"💰 Amount: **${amount:.2f} USDT**\n"
                                         f"📊 Your balance: **${user.balance:.2f}**\n\n"
                                         f"🌱 You can now invest!",
                                    parse_mode='Markdown'
                                )
                            except Exception as e:
                                logger.error(f"Error sending notification: {e}")
                
                except Exception as e:
                    logger.error(f"Error processing user {user.telegram_id}: {e}")
                    continue

            session.close()

        except Exception as e:
            logger.error(f"Error in deposit scanner: {e}")

    async def _get_recent_usdt_transfers(self):
        """Fetch recent USDT token transfers to the project wallet from BSCScan"""
        try:
            # Get current block number (approx)
            current_block = await self._get_current_block()
            if not current_block:
                logger.error("Failed to get current block")
                return []
            
            start_block = current_block - 1000  # check last 1000 blocks
            if start_block < 0:
                start_block = 0
            
            # BSCScan API endpoint for token transfers
            url = (
                f"{Config.BSC_SCAN_API}"
                f"?module=account"
                f"&action=tokentx"
                f"&contractaddress={self.usdt_contract}"
                f"&address={self.project_wallet}"
                f"&startblock={start_block}"
                f"&endblock={current_block}"
                f"&sort=desc"
                f"&apikey={self.api_key}"
            )
            
            logger.info(f"🔍 Fetching USDT transfers from BSCScan...")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"BSCScan HTTP error: {response.status}")
                        return []
                    
                    data = await response.json()
                    if data.get('status') != '1':
                        logger.warning(f"BSCScan API error: {data.get('message')}")
                        return []
                    
                    transactions = data.get('result', [])
                    logger.info(f"✅ Found {len(transactions)} USDT transfers")
                    
                    # Filter only transfers TO the project wallet (should already be filtered, but double-check)
                    transfers = [
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
                    
                    return transfers
                    
        except asyncio.TimeoutError:
            logger.error("BSCScan timeout")
            return []
        except Exception as e:
            logger.error(f"Error fetching transfers: {e}")
            return []

    async def _get_current_block(self):
        """Get current BSC block number via RPC"""
        try:
            url = Config.BSC_RPC_URL
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    data = await response.json()
                    if data and data.get('result'):
                        return int(data.get('result', '0'), 16)
                    return None
        except Exception as e:
            logger.error(f"Error getting block: {e}")
            return None

    async def check_deposit_with_amount(self, user_id: int, expected_amount: float, bot):
        """Fallback method: check project wallet balance (used when user clicks button)"""
        try:
            logger.info(f"🔍 Manual deposit check for user {user_id}, expected: ${expected_amount:.2f}")
            session = self.db.get_session()

            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            if not user.wallet_address:
                return {'success': False, 'message': 'No wallet connected'}

            # First, try to find a recent transfer via BSCScan
            transfers = await self._get_recent_usdt_transfers()
            for tx in transfers:
                if tx['from'].lower() == user.wallet_address.lower():
                    # Check if already processed
                    existing = session.query(Deposit).filter_by(tx_hash=tx['hash']).first()
                    if existing:
                        # Check if balance is correct
                        expected_balance = user.total_deposited - user.total_invested + user.total_earnings_all_time
                        if user.balance < expected_balance:
                            user.balance += expected_amount
                            session.commit()
                            return {'success': True, 'message': 'Balance corrected'}
                        return {'success': True, 'message': 'Deposit already processed'}
                    
                    # Process new deposit
                    amount = float(tx['value']) / 10**18
                    deposit = Deposit(
                        user_id=user.id,
                        amount=amount,
                        tx_hash=tx['hash'],
                        from_address=tx['from'],
                        block_number=tx['block_number'],
                        confirmed_at=datetime.utcnow(),
                        processed=True
                    )
                    session.add(deposit)
                    user.balance += amount
                    user.total_deposited += amount
                    session.commit()
                    logger.info(f"✅ Deposit processed via manual check: ${amount:.2f}")
                    return {'success': True, 'message': 'Deposit detected and processed'}

            # Fallback to balance check
            project_balance = await self._get_usdt_balance(self.project_wallet)
            if project_balance >= expected_amount:
                # Process as before (but this is less reliable)
                deposit = Deposit(
                    user_id=user.id,
                    amount=expected_amount,
                    tx_hash=f"0xmanual_{datetime.utcnow().timestamp()}",
                    from_address=user.wallet_address,
                    block_number=0,
                    confirmed_at=datetime.utcnow(),
                    processed=True
                )
                session.add(deposit)
                user.balance += expected_amount
                user.total_deposited += expected_amount
                session.commit()
                logger.info(f"✅ Deposit processed via balance fallback: ${expected_amount:.2f}")
                return {'success': True, 'message': 'Deposit detected and processed'}
            
            return {'success': False, 'message': 'No new deposit found'}

        except Exception as e:
            logger.error(f"Error in check_deposit_with_amount: {e}")
            session.rollback()
            return {'success': False, 'message': str(e)}

    async def _get_usdt_balance(self, wallet_address: str) -> float:
        """Get USDT balance (for fallback)"""
        try:
            usdt_contract = Config.USDT_CONTRACT
            data = f"0x70a08231000000000000000000000000{wallet_address[2:].lower()}"
            url = Config.BSC_RPC_URL
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [{"to": usdt_contract, "data": data}, "latest"],
                "id": 1
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    data = await response.json()
                    if data and data.get('result'):
                        balance = int(data.get('result'), 16)
                        return balance / 10**18
                    return 0
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0

import aiohttp
import asyncio
from datetime import datetime, timedelta
from database.db_manager import DatabaseManager
from database.models import User, Deposit
from config.settings import Config
import logging
import json

logger = logging.getLogger(__name__)

class DepositScanner:
    def __init__(self):
        self.db = DatabaseManager()
        self.project_wallet = Config.WALLET_ADDRESS.lower()
        self.usdt_contract = Config.USDT_CONTRACT.lower()
        self.rpc_url = Config.BSC_RPC_URL
        self.scan_interval = 300  # 5 minutes

    async def scan_for_deposits(self, bot):
        """Scan for new deposits using BSC RPC eth_getLogs"""
        try:
            logger.info("🔍 Scanning for new deposits via RPC logs...")
            session = self.db.get_session()

            users = session.query(User).filter(
                User.wallet_address.isnot(None),
                User.wallet_address != ''
            ).all()

            if not users:
                logger.info("No users with wallets found")
                session.close()
                return

            # Get recent USDT Transfer events to the project wallet
            transfers = await self._get_usdt_transfers()
            if not transfers:
                logger.info("No recent USDT transfers found")
                session.close()
                return

            # Process each transfer
            for tx in transfers:
                to_addr = tx['to'].lower()
                if to_addr != self.project_wallet:
                    continue

                from_addr = tx['from'].lower()
                amount = tx['value']

                # Find user with matching wallet
                user = session.query(User).filter_by(wallet_address=from_addr).first()
                if not user:
                    logger.info(f"❌ No user found for wallet {from_addr[:10]}...")
                    continue

                # Check if already processed
                existing = session.query(Deposit).filter_by(tx_hash=tx['hash']).first()
                if existing:
                    continue

                # Process deposit
                deposit = Deposit(
                    user_id=user.id,
                    amount=amount,
                    tx_hash=tx['hash'],
                    from_address=from_addr,
                    block_number=tx['block_number'],
                    confirmed_at=datetime.utcnow(),
                    processed=True
                )
                session.add(deposit)

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
                                 f"🌱 You can now invest in planting fields!",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Error sending notification: {e}")

            session.close()

        except Exception as e:
            logger.error(f"Error in deposit scanner: {e}")

    async def _get_usdt_transfers(self, blocks_back: int = 2000):
        """Fetch USDT Transfer events via BSC RPC eth_getLogs"""
        try:
            # Get current block
            current_block = await self._get_current_block()
            if not current_block:
                logger.error("Failed to get current block")
                return []

            from_block = current_block - blocks_back
            if from_block < 0:
                from_block = 0

            # USDT Transfer event signature: Transfer(address,address,uint256)
            # topic0 = 0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef
            event_signature = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

            # Filter for transfers TO the project wallet
            # topic2 is the 'to' address (indexed)
            # Pad the address to 32 bytes
            to_topic = "0x" + "0" * 24 + self.project_wallet[2:]

            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getLogs",
                "params": [{
                    "fromBlock": hex(from_block),
                    "toBlock": hex(current_block),
                    "address": self.usdt_contract,
                    "topics": [
                        event_signature,
                        None,  # from (any)
                        to_topic  # to = project wallet
                    ]
                }],
                "id": 1
            }

            logger.info(f"🔍 Fetching USDT transfer logs from blocks {from_block} to {current_block}")

            async with aiohttp.ClientSession() as session:
                async with session.post(self.rpc_url, json=payload, timeout=30) as response:
                    if response.status != 200:
                        logger.error(f"RPC error: {response.status}")
                        return []

                    data = await response.json()
                    if 'error' in data:
                        logger.error(f"RPC error: {data['error']}")
                        return []

                    logs = data.get('result', [])
                    logger.info(f"✅ Found {len(logs)} USDT transfer logs")

                    transfers = []
                    for log in logs:
                        # Decode the log
                        # topics[1] = from (indexed), topics[2] = to (indexed)
                        # data = amount (uint256)
                        try:
                            from_addr = "0x" + log['topics'][1][-40:]
                            to_addr = "0x" + log['topics'][2][-40:]
                            amount_hex = log['data']
                            amount = int(amount_hex, 16) / 10**18

                            if amount < 0.01:
                                continue  # ignore tiny amounts

                            transfers.append({
                                'hash': log['transactionHash'],
                                'from': from_addr,
                                'to': to_addr,
                                'value': amount,
                                'block_number': int(log['blockNumber'], 16),
                            })
                        except Exception as e:
                            logger.error(f"Error decoding log: {e}")
                            continue

                    # Sort by block number (newest first)
                    transfers.sort(key=lambda x: x['block_number'], reverse=True)
                    return transfers

        except asyncio.TimeoutError:
            logger.error("RPC timeout")
            return []
        except Exception as e:
            logger.error(f"Error fetching transfers: {e}")
            return []

    async def _get_current_block(self):
        """Get current BSC block number via RPC"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_blockNumber",
                "params": [],
                "id": 1
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(self.rpc_url, json=payload, timeout=10) as response:
                    data = await response.json()
                    if data and data.get('result'):
                        return int(data.get('result', '0'), 16)
                    return None
        except Exception as e:
            logger.error(f"Error getting block: {e}")
            return None

    async def check_deposit_with_amount(self, user_id: int, expected_amount: float, bot):
        """Manual deposit check (button fallback)"""
        try:
            logger.info(f"🔍 Manual deposit check for user {user_id}, expected: ${expected_amount:.2f}")
            session = self.db.get_session()

            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                return {'success': False, 'message': 'User not found'}
            if not user.wallet_address:
                return {'success': False, 'message': 'No wallet connected'}

            # Use the log scanner to find recent transfers
            transfers = await self._get_usdt_transfers(blocks_back=5000)
            for tx in transfers:
                if tx['from'].lower() == user.wallet_address.lower() and tx['to'].lower() == self.project_wallet:
                    # Check if already processed
                    existing = session.query(Deposit).filter_by(tx_hash=tx['hash']).first()
                    if existing:
                        # Check balance
                        expected_balance = user.total_deposited - user.total_invested + user.total_earnings_all_time
                        if user.balance < expected_balance:
                            user.balance += tx['value']
                            session.commit()
                            return {'success': True, 'message': 'Balance corrected'}
                        return {'success': True, 'message': 'Deposit already processed'}

                    # Process new deposit
                    deposit = Deposit(
                        user_id=user.id,
                        amount=tx['value'],
                        tx_hash=tx['hash'],
                        from_address=tx['from'],
                        block_number=tx['block_number'],
                        confirmed_at=datetime.utcnow(),
                        processed=True
                    )
                    session.add(deposit)
                    user.balance += tx['value']
                    user.total_deposited += tx['value']
                    session.commit()
                    logger.info(f"✅ Deposit processed via manual check: ${tx['value']:.2f}")
                    return {'success': True, 'message': 'Deposit detected and processed'}

            return {'success': False, 'message': 'No new deposit found'}

        except Exception as e:
            logger.error(f"Error in check_deposit_with_amount: {e}")
            session.rollback()
            return {'success': False, 'message': str(e)}

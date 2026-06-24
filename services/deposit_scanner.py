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
        # List of RPC endpoints to try
        self.rpc_urls = [
            Config.BSC_RPC_URL,
            "https://bsc-dataseed1.defibit.io/",
            "https://bsc-dataseed2.binance.org/",
            "https://bsc-dataseed3.binance.org/",
        ]
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

    async def _get_usdt_transfers(self, initial_blocks: int = 200):
        """Fetch USDT Transfer events via BSC RPC eth_getLogs with adaptive range"""
        try:
            current_block = await self._get_current_block()
            if not current_block:
                logger.error("Failed to get current block")
                return []

            # Try different block ranges and RPC endpoints
            ranges = [initial_blocks, 100, 50, 20, 10]
            logs = None

            for block_range in ranges:
                from_block = current_block - block_range
                if from_block < 0:
                    from_block = 0

                logger.info(f"🔍 Trying block range {block_range} (from {from_block} to {current_block})")

                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_getLogs",
                    "params": [{
                        "fromBlock": hex(from_block),
                        "toBlock": hex(current_block),
                        "address": self.usdt_contract,
                        "topics": [
                            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                            None,
                            "0x" + "0" * 24 + self.project_wallet[2:]
                        ]
                    }],
                    "id": 1
                }

                # Try each RPC endpoint
                for rpc_url in self.rpc_urls:
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.post(rpc_url, json=payload, timeout=15) as response:
                                if response.status != 200:
                                    continue
                                data = await response.json()
                                if 'error' in data:
                                    if 'limit exceeded' in data['error'].get('message', ''):
                                        logger.warning(f"Limit exceeded for range {block_range} on {rpc_url}")
                                        continue
                                    else:
                                        logger.error(f"RPC error: {data['error']}")
                                        continue
                                logs = data.get('result', [])
                                if logs:
                                    logger.info(f"✅ Found {len(logs)} logs with range {block_range} on {rpc_url}")
                                    # Break out of RPC loop and range loop
                                    break
                    except Exception as e:
                        logger.warning(f"RPC {rpc_url} failed: {e}")
                        continue

                if logs:
                    break

            if logs is None:
                logger.error("All block ranges and RPC endpoints failed")
                return []

            # Process logs
            transfers = []
            for log in logs:
                try:
                    from_addr = "0x" + log['topics'][1][-40:]
                    to_addr = "0x" + log['topics'][2][-40:]
                    amount_hex = log['data']
                    amount = int(amount_hex, 16) / 10**18

                    if amount < 0.01:
                        continue

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

            transfers.sort(key=lambda x: x['block_number'], reverse=True)
            logger.info(f"✅ Decoded {len(transfers)} USDT transfers")
            return transfers

        except Exception as e:
            logger.error(f"Error fetching transfers: {e}")
            return []

    async def _get_current_block(self):
        """Get current BSC block number via RPC"""
        for rpc_url in self.rpc_urls:
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_blockNumber",
                    "params": [],
                    "id": 1
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(rpc_url, json=payload, timeout=10) as response:
                        data = await response.json()
                        if data and data.get('result'):
                            return int(data.get('result', '0'), 16)
            except Exception as e:
                logger.warning(f"Block RPC {rpc_url} failed: {e}")
                continue
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
            transfers = await self._get_usdt_transfers(initial_blocks=500)
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

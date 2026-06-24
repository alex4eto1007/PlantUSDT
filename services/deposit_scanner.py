import aiohttp
import asyncio
from datetime import datetime
from database.db_manager import DatabaseManager
from database.models import User, Deposit
from config.settings import Config
import logging

logger = logging.getLogger(__name__)

class DepositScanner:
    def __init__(self):
        self.db = DatabaseManager()
        self.project_wallet = Config.WALLET_ADDRESS.lower()
        self.usdt_contract = Config.USDT_CONTRACT.lower()
        self.rpc_url = Config.BSC_RPC_URL
        self.scan_interval = 300

    async def scan_for_deposits(self, bot):
        """Simple scanner: just log balances (manual detection via button)"""
        try:
            logger.info("🔍 Checking balances...")
            session = self.db.get_session()
            users = session.query(User).filter(
                User.wallet_address.isnot(None),
                User.wallet_address != ''
            ).all()
            for user in users:
                try:
                    balance = await self._get_usdt_balance(user.wallet_address)
                    logger.info(f"📊 User {user.telegram_id} USDT balance: ${balance:.2f}")
                except Exception as e:
                    logger.error(f"Error: {e}")
            session.close()
        except Exception as e:
            logger.error(f"Scanner error: {e}")

    async def check_deposit_with_amount(self, user_id: int, expected_amount: float, bot):
        """Manual deposit check - triggered by user clicking 'I've Sent USDT'"""
        try:
            logger.info(f"🔍 Manual deposit check for user {user_id}, expected: ${expected_amount:.2f}")
            session = self.db.get_session()

            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                return {'success': False, 'message': 'User not found'}
            if not user.wallet_address:
                return {'success': False, 'message': 'No wallet connected'}

            # Check current project wallet balance
            current_balance = await self._get_usdt_balance(self.project_wallet)
            logger.info(f"📊 Project wallet balance: ${current_balance:.2f}")

            # Check if user already has a deposit of this amount
            existing = session.query(Deposit).filter_by(
                user_id=user.id,
                amount=expected_amount
            ).first()

            if existing:
                # Check if balance already reflects it
                expected_balance = user.total_deposited - user.total_invested + user.total_earnings_all_time
                if user.balance < expected_balance:
                    user.balance += expected_amount
                    session.commit()
                    logger.info(f"✅ Balance corrected: ${user.balance:.2f}")
                    return {'success': True, 'message': 'Balance corrected'}
                return {'success': True, 'message': 'Deposit already processed'}

            # If project wallet has the funds, credit the user
            if current_balance >= expected_amount:
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
                logger.info(f"✅ Deposit processed: ${expected_amount:.2f}")
                return {'success': True, 'message': 'Deposit detected and processed'}

            return {'success': False, 'message': f'No deposit of ${expected_amount:.2f} found'}

        except Exception as e:
            logger.error(f"Error: {e}")
            session.rollback()
            return {'success': False, 'message': str(e)}

    async def _get_usdt_balance(self, wallet_address: str) -> float:
        """Simple USDT balance check via RPC"""
        try:
            data = f"0x70a08231000000000000000000000000{wallet_address[2:].lower()}"
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_call",
                "params": [{"to": self.usdt_contract, "data": data}, "latest"],
                "id": 1
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(self.rpc_url, json=payload, timeout=10) as response:
                    data = await response.json()
                    if data and data.get('result'):
                        return int(data.get('result'), 16) / 10**18
                    return 0
        except Exception as e:
            logger.error(f"Balance error: {e}")
            return 0

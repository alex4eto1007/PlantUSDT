import aiohttp
import asyncio
from datetime import datetime
from database.db_manager import DatabaseManager
from database.models import User, Deposit
from config.settings import Config
from services.notifications import NotificationService
import logging

logger = logging.getLogger(__name__)

class DepositScanner:
    def __init__(self):
        self.db = DatabaseManager()
        self.notification_service = NotificationService()
        self.project_wallet = Config.WALLET_ADDRESS.lower()
        self.usdt_contract = Config.USDT_CONTRACT.lower()
        self.rpc_url = Config.POLYGON_RPC_URL
        self.api_url = Config.ETHERSCAN_API_V2_URL
        self.api_key = Config.ETHERSCAN_API_KEY
        self.chain_id = Config.POLYGON_CHAIN_ID
        self.network = "Polygon"
        self.decimals = Config.USDT_DECIMALS
        self.scan_interval = 300

    async def scan_for_deposits(self, bot):
        """Scan for deposits on Polygon using Etherscan V2 API"""
        try:
            logger.info("🔍 Scanning for Polygon deposits...")
            session = self.db.get_session()
            users = session.query(User).filter(
                User.wallet_address.isnot(None),
                User.wallet_address != ''
            ).all()
            
            for user in users:
                try:
                    await self._check_user_deposits(user, bot)
                except Exception as e:
                    logger.error(f"Error checking user {user.telegram_id}: {e}")
            
            session.close()
        except Exception as e:
            logger.error(f"Scanner error: {e}")

    async def _check_user_deposits(self, user, bot):
        """Check for new deposits from a specific user on Polygon using V2 API"""
        try:
            url = f"{self.api_url}?chainid={self.chain_id}&module=account&action=tokentx&address={user.wallet_address}&contractaddress={self.usdt_contract}&page=1&offset=50&sort=desc&apikey={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    data = await response.json()
                    
                    if data.get('status') != '1':
                        logger.debug(f"No transactions found for user {user.telegram_id} on Polygon")
                        return
                    
                    transactions = data.get('result', [])
                    
                    for tx in transactions:
                        if tx.get('to', '').lower() == self.project_wallet:
                            existing = self.db.get_deposit_by_tx_hash(tx.get('hash'))
                            if existing:
                                continue
                            
                            amount = int(tx.get('value', '0')) / 10**self.decimals
                            
                            await self._process_deposit(
                                user=user,
                                amount=amount,
                                tx_hash=tx.get('hash'),
                                from_address=tx.get('from'),
                                block_number=int(tx.get('blockNumber', 0)),
                                bot=bot
                            )
                            
        except Exception as e:
            logger.error(f"Error checking user deposits on Polygon: {e}")

    async def _process_deposit(self, user, amount, tx_hash, from_address, block_number, bot):
        """Process a verified deposit on Polygon"""
        try:
            session = self.db.get_session()
            
            is_valid = await self._verify_transaction(tx_hash)
            if not is_valid:
                logger.warning(f"⚠️ Invalid transaction detected: {tx_hash} on Polygon")
                return
            
            existing = session.query(Deposit).filter_by(tx_hash=tx_hash).first()
            if existing:
                logger.info(f"Deposit {tx_hash} already processed on Polygon")
                return
            
            deposit = Deposit(
                user_id=user.id,
                amount=amount,
                tx_hash=tx_hash,
                from_address=from_address,
                block_number=block_number,
                network='polygon'
            )
            session.add(deposit)
            
            user.balance += amount
            user.total_deposited += amount
            
            session.commit()
            logger.info(f"✅ Deposit processed on Polygon: {user.telegram_id} +${amount:.2f} USDT")
            
            try:
                await self.notification_service.send_deposit_notification(
                    user_id=user.telegram_id,
                    amount=amount,
                    tx_hash=tx_hash
                )
            except Exception as e:
                logger.error(f"Error sending deposit notification: {e}")
            
            try:
                message = (
                    f"💰 **Deposit Detected on Polygon!**\n\n"
                    f"Amount: **${amount:.2f} USDT**\n"
                    f"Network: **Polygon** ⛓️\n"
                    f"TX: `{tx_hash[:10]}...{tx_hash[-8:]}`\n\n"
                    f"🌱 Your balance: **${user.balance:.2f}**\n"
                    f"💎 Total deposited: **${user.total_deposited:.2f}**"
                )
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"✅ Deposit notification sent to {user.telegram_id}")
            except Exception as e:
                logger.error(f"Error sending deposit notification: {e}")
                
        except Exception as e:
            logger.error(f"Error processing deposit on Polygon: {e}")
            session.rollback()
        finally:
            session.close()

    async def _verify_transaction(self, tx_hash: str) -> bool:
        """Verify transaction is valid and is USDT on Polygon using V2 API"""
        try:
            url = f"{self.api_url}?chainid={self.chain_id}&module=transaction&action=gettxreceiptstatus&txhash={tx_hash}&apikey={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    data = await response.json()
                    
                    if data.get('status') != '1':
                        logger.warning(f"Transaction {tx_hash} not found on Polygon")
                        return False
                    
                    receipt = data.get('result', {})
                    logs = receipt.get('logs', [])
                    
                    for log in logs:
                        if log.get('address', '').lower() == self.usdt_contract:
                            return True
                    
                    logger.warning(f"No USDT transfer found in transaction {tx_hash} on Polygon")
                    return False
                    
        except Exception as e:
            logger.error(f"Error verifying transaction on Polygon: {e}")
            return False

    async def _get_usdt_balance(self, wallet_address: str) -> float:
        """Get USDT balance on Polygon using Etherscan V2 API (FREE)"""
        try:
            url = f"{self.api_url}?chainid={self.chain_id}&module=account&action=tokenbalance&contractaddress={self.usdt_contract}&address={wallet_address}&tag=latest&apikey={self.api_key}"
            
            logger.info(f"🔍 Fetching balance from: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    data = await response.json()
                    logger.info(f"📦 Balance API Response: {data}")
                    
                    if data and data.get('status') == '1':
                        result = data.get('result', '0')
                        if result and result != '0':
                            balance = int(result) / 10**self.decimals
                            logger.info(f"💰 Balance found: ${balance:.2f} USDT")
                            return balance
                        else:
                            logger.info(f"💰 Balance is zero or empty")
                            return 0.0
                    else:
                        logger.error(f"❌ API V2 error: {data.get('message', 'Unknown error')}")
                        return 0.0
        except Exception as e:
            logger.error(f"❌ Balance error on Polygon: {e}")
            return 0.0

    async def check_deposit_with_amount(self, user_id: int, expected_amount: float, bot):
        """Manual deposit check - triggered by user clicking 'I've Sent USDT' on Polygon"""
        try:
            logger.info(f"🔍 Manual deposit check for user {user_id}, expected: ${expected_amount:.2f} on Polygon")
            session = self.db.get_session()

            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                return {'success': False, 'message': 'User not found'}
            if not user.wallet_address:
                return {'success': False, 'message': 'No wallet connected'}

            url = f"{self.api_url}?chainid={self.chain_id}&module=account&action=tokentx&address={user.wallet_address}&contractaddress={self.usdt_contract}&page=1&offset=10&sort=desc&apikey={self.api_key}"
            
            async with aiohttp.ClientSession() as session_api:
                async with session_api.get(url, timeout=30) as response:
                    data = await response.json()
                    
                    if data.get('status') == '1':
                        transactions = data.get('result', [])
                        for tx in transactions:
                            if tx.get('to', '').lower() == self.project_wallet:
                                amount = int(tx.get('value', '0')) / 10**self.decimals
                                if abs(amount - expected_amount) < 0.01:
                                    existing = session.query(Deposit).filter_by(tx_hash=tx.get('hash')).first()
                                    if not existing:
                                        await self._process_deposit(
                                            user=user,
                                            amount=amount,
                                            tx_hash=tx.get('hash'),
                                            from_address=tx.get('from'),
                                            block_number=int(tx.get('blockNumber', 0)),
                                            bot=bot
                                        )
                                        return {'success': True, 'message': f'Deposit of ${amount:.2f} USDT detected and processed on Polygon!'}
                                    else:
                                        return {'success': True, 'message': 'Deposit already processed'}
            
            return {'success': False, 'message': f'No deposit of ${expected_amount:.2f} USDT found on Polygon. Please make sure you sent USDT on the Polygon network.'}

        except Exception as e:
            logger.error(f"Error in manual deposit check on Polygon: {e}")
            if 'session' in locals():
                session.rollback()
            return {'success': False, 'message': str(e)}
        finally:
            if 'session' in locals():
                session.close()

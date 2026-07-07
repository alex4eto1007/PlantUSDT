import aiohttp
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from database.db_manager import DatabaseManager
from database.models import User, Deposit, PendingDepositCheck
from config.settings import Config
from services.notifications import NotificationService
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

try:
    from bot.api import clear_user_cache
except ImportError:
    def clear_user_cache(telegram_id):
        logger.info(f"Cache cleared for user {telegram_id} (fallback)")
        return True

class DepositScanner:
    def __init__(self):
        self.db = DatabaseManager()
        self.notification_service = NotificationService()
        self.project_wallet = Config.WALLET_ADDRESS.lower()
        self.usdt_contract = Config.USDT_CONTRACT.lower()
        self.rpc_url = Config.POLYGON_RPC_URL
        self.api_url = Config.POLYGONSCAN_API_URL
        self.api_key = Config.ETHERSCAN_API_KEY
        self.chain_id = Config.POLYGON_CHAIN_ID
        self.network = "Polygon"
        self.decimals = Config.USDT_DECIMALS
        self.scan_interval = 300

    async def scan_for_deposits(self, bot):
        """Scan only users with pending deposit checks (last 30 minutes)"""
        try:
            logger.info("🔍 Scanning pending deposits...")
            session = self.db.get_session()
            
            cutoff = datetime.utcnow() - timedelta(minutes=30)
            
            pending = session.query(PendingDepositCheck).filter(
                PendingDepositCheck.created_at > cutoff,
                PendingDepositCheck.checked == False
            ).all()
            
            if not pending:
                logger.info("📊 No pending deposit checks")
                session.close()
                return
            
            logger.info(f"📊 Found {len(pending)} pending deposit checks")
            
            for pending_check in pending:
                user = session.query(User).filter_by(id=pending_check.user_id).first()
                if user:
                    try:
                        await self._check_user_deposit_with_amount(user, float(pending_check.amount), bot)
                        pending_check.checked = True
                        session.commit()
                    except Exception as e:
                        logger.error(f"Error checking pending deposit for user {user.telegram_id}: {e}")
            
            session.close()
        except Exception as e:
            logger.error(f"Scanner error: {e}")

    async def _check_user_deposit_with_amount(self, user, expected_amount, bot):
        """Check if a specific user has made a deposit with the expected amount"""
        try:
            url = f"{self.api_url}&module=account&action=tokentx&address={user.wallet_address}&contractaddress={self.usdt_contract}&page=1&offset=10&sort=desc&apikey={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    data = await response.json()
                    
                    if data.get('status') == '1':
                        transactions = data.get('result', [])
                        for tx in transactions:
                            if tx.get('to', '').lower() == self.project_wallet:
                                amount = int(tx.get('value', '0')) / 10**self.decimals
                                if abs(float(amount) - float(expected_amount)) < 0.01:
                                    await self._process_deposit(
                                        user=user,
                                        amount=amount,
                                        tx_hash=tx.get('hash'),
                                        from_address=tx.get('from'),
                                        block_number=int(tx.get('blockNumber', 0)),
                                        bot=bot
                                    )
                                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking user deposit: {e}")
            return False

    async def _process_deposit(self, user, amount, tx_hash, from_address, block_number, bot):
        """Process a verified deposit on Polygon and send to channel"""
        try:
            session = self.db.get_session()
            
            fresh_user = session.query(User).filter_by(id=user.id).first()
            if not fresh_user:
                logger.error(f"User {user.id} not found in database")
                session.close()
                return
            
            is_valid = await self._verify_transaction(tx_hash)
            if not is_valid:
                logger.warning(f"⚠️ Invalid transaction detected: {tx_hash} on Polygon")
                session.close()
                return
            
            existing = session.query(Deposit).filter_by(tx_hash=tx_hash).first()
            if existing:
                if existing.processed:
                    logger.info(f"Deposit {tx_hash} already processed on Polygon")
                else:
                    logger.info(f"Deposit {tx_hash} found but not processed, processing now...")
                    existing.processed = True
                    deposit_amount = Decimal(str(amount))
                    fresh_user.balance = (fresh_user.balance or Decimal('0')) + deposit_amount
                    fresh_user.total_deposited = (fresh_user.total_deposited or Decimal('0')) + deposit_amount
                    session.commit()
                    logger.info(f"✅ Deposit processed on Polygon: {fresh_user.telegram_id} +${amount:.2f} USDT")
                    clear_user_cache(fresh_user.telegram_id)
                    await self._send_notifications(fresh_user, amount, tx_hash, bot)
                session.close()
                return
            
            deposit = Deposit(
                user_id=fresh_user.id,
                amount=amount,
                tx_hash=tx_hash,
                from_address=from_address,
                block_number=block_number,
                network='polygon',
                processed=True
            )
            session.add(deposit)
            
            deposit_amount = Decimal(str(amount))
            fresh_user.balance = (fresh_user.balance or Decimal('0')) + deposit_amount
            fresh_user.total_deposited = (fresh_user.total_deposited or Decimal('0')) + deposit_amount
            
            session.commit()
            logger.info(f"✅ Deposit processed on Polygon: {fresh_user.telegram_id} +${amount:.2f} USDT")
            
            clear_user_cache(fresh_user.telegram_id)
            await self._send_notifications(fresh_user, amount, tx_hash, bot)
            
        except Exception as e:
            logger.error(f"Error processing deposit on Polygon: {e}")
            if 'session' in locals():
                session.rollback()
        finally:
            if 'session' in locals():
                session.close()

    async def _send_notifications(self, user, amount, tx_hash, bot):
        """Send deposit notifications to user and channel"""
        logger.info(f"🔔 Sending notifications for deposit: ${amount:.2f}")
        
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
        
        # Send to transaction channel
        try:
            channel_message = (
                f"💰 **New Deposit!**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 Amount: **${amount:.2f} USDT**\n"
                f"⛓️ Network: Polygon\n"
                f"🔗 TX: [View on Polygonscan](https://polygonscan.com/tx/{tx_hash})\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🏦 Project Wallet: `{Config.WALLET_ADDRESS}`"
            )
            await bot.send_message(
                chat_id=-1004391112772,
                text=channel_message,
                parse_mode='Markdown'
            )
            logger.info("✅ Deposit posted to transaction channel")
        except Exception as e:
            logger.error(f"❌ Failed to send deposit to channel: {e}")

    async def _verify_transaction(self, tx_hash: str) -> bool:
        """Verify transaction is a valid USDT transfer using V2 API"""
        try:
            url = f"{self.api_url}&module=transaction&action=gettxreceiptstatus&txhash={tx_hash}&apikey={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    data = await response.json()
                    
                    if data.get('status') != '1':
                        logger.warning(f"Transaction {tx_hash} not found or failed on Polygon")
                        return False
                    
                    result = data.get('result', {})
                    if result.get('status') != '1':
                        logger.warning(f"Transaction {tx_hash} failed (status: {result.get('status')})")
                        return False
            
            token_url = f"{self.api_url}&module=account&action=tokentx&address={self.project_wallet}&contractaddress={self.usdt_contract}&page=1&offset=10&sort=desc&apikey={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(token_url, timeout=15) as response:
                    data = await response.json()
                    
                    if data.get('status') == '1':
                        transactions = data.get('result', [])
                        for tx in transactions:
                            if tx.get('hash') == tx_hash:
                                amount = int(tx.get('value', '0')) / 10**self.decimals
                                logger.info(f"✅ Found USDT transfer in transaction {tx_hash[:16]}... Amount: ${amount:.2f}")
                                return True
            
            logger.warning(f"No USDT transfer found in transaction {tx_hash}")
            return False
                    
        except Exception as e:
            logger.error(f"Error verifying transaction on Polygon: {e}")
            return False

    async def _get_usdt_balance(self, wallet_address: str) -> float:
        """Get USDT balance using V2 API"""
        try:
            url = f"{self.api_url}&module=account&action=tokenbalance&contractaddress={self.usdt_contract}&address={wallet_address}&tag=latest&apikey={self.api_key}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    data = await response.json()
                    
                    if data and data.get('status') == '1':
                        result = data.get('result', '0')
                        if result and result != '0':
                            balance = float(result) / (10 ** self.decimals)
                            return balance
                    return 0.0
        except Exception as e:
            logger.error(f"❌ Balance error on Polygon: {e}")
            return 0.0

    async def check_deposit_with_amount(self, user_id: int, expected_amount: float, bot):
        """Manual deposit check using V2 API"""
        try:
            logger.info(f"🔍 Manual deposit check for user {user_id}, expected: ${expected_amount:.2f} on Polygon")
            session = self.db.get_session()

            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                return {'success': False, 'message': 'User not found'}
            if not user.wallet_address:
                return {'success': False, 'message': 'No wallet connected'}

            # Create pending check record
            pending = PendingDepositCheck(
                user_id=user.id,
                amount=expected_amount
            )
            session.add(pending)
            session.commit()

            # Check for existing processed deposit first
            existing_deposit = session.query(Deposit).filter_by(
                user_id=user.id,
                processed=True
            ).order_by(Deposit.id.desc()).first()
            
            if existing_deposit and abs(float(existing_deposit.amount) - float(expected_amount)) < 0.01:
                time_diff = (datetime.utcnow() - existing_deposit.confirmed_at).total_seconds() / 60
                if time_diff < 60:
                    pending.checked = True
                    session.commit()
                    session.close()
                    return {'success': True, 'message': f'Deposit of ${existing_deposit.amount:.2f} USDT already processed! Balance updated.'}

            url = f"{self.api_url}&module=account&action=tokentx&address={user.wallet_address}&contractaddress={self.usdt_contract}&page=1&offset=10&sort=desc&apikey={self.api_key}"
            
            async with aiohttp.ClientSession() as session_api:
                async with session_api.get(url, timeout=30) as response:
                    data = await response.json()
                    
                    if data.get('status') == '1':
                        transactions = data.get('result', [])
                        for tx in transactions:
                            if tx.get('to', '').lower() == self.project_wallet:
                                amount = int(tx.get('value', '0')) / 10**self.decimals
                                if abs(float(amount) - float(expected_amount)) < 0.01:
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
                                        pending.checked = True
                                        session.commit()
                                        session.close()
                                        return {'success': True, 'message': f'Deposit of ${amount:.2f} USDT detected and processed on Polygon!'}
                                    elif not existing.processed:
                                        existing.processed = True
                                        deposit_amount = Decimal(str(amount))
                                        user.balance = (user.balance or Decimal('0')) + deposit_amount
                                        user.total_deposited = (user.total_deposited or Decimal('0')) + deposit_amount
                                        session.commit()
                                        clear_user_cache(user.telegram_id)
                                        await self._send_notifications(user, amount, tx.get('hash'), bot)
                                        pending.checked = True
                                        session.commit()
                                        session.close()
                                        return {'success': True, 'message': f'Deposit of ${amount:.2f} USDT processed successfully!'}
                                    else:
                                        pending.checked = True
                                        session.commit()
                                        session.close()
                                        return {'success': True, 'message': f'Deposit of ${amount:.2f} USDT already processed! Check your balance.'}
            
            pending.checked = True
            session.commit()
            session.close()
            return {'success': False, 'message': f'No deposit of ${expected_amount:.2f} USDT found on Polygon. Please make sure you sent USDT on the Polygon network.'}

        except Exception as e:
            logger.error(f"Error in manual deposit check on Polygon: {e}")
            if 'session' in locals():
                session.rollback()
            return {'success': False, 'message': str(e)}
        finally:
            if 'session' in locals():
                session.close()

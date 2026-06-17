from web3 import Web3
from web3.middleware import geth_poa_middleware
from config.settings import Config
import json
import requests
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class WalletService:
    def __init__(self):
        # BSC RPC Connection
        self.w3 = Web3(Web3.HTTPProvider(Config.BSC_RPC_URL))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # USDT BSC Contract ABI (BEP-20)
        self.usdt_abi = json.loads('''[
            {"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"},
            {"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"},
            {"constant":true,"inputs":[{"name":"_owner","type":"address"},{"name":"_spender","type":"address"}],"name":"allowance","outputs":[{"name":"","type":"uint256"}],"type":"function"},
            {"anonymous":false,"inputs":[{"indexed":true,"name":"from","type":"address"},{"indexed":true,"name":"to","type":"address"},{"indexed":false,"name":"value","type":"uint256"}],"name":"Transfer","type":"event"}
        ]''')
        
        self.usdt_contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(Config.USDT_CONTRACT),
            abi=self.usdt_abi
        )
        
        self.wallet_address = Web3.to_checksum_address(Config.WALLET_ADDRESS)
        self.decimals = self.usdt_contract.functions.decimals().call()
        self.last_checked_block = None
        
    def get_usdt_balance(self, address: str) -> float:
        """Get USDT BEP-20 balance for an address"""
        try:
            balance = self.usdt_contract.functions.balanceOf(
                Web3.to_checksum_address(address)
            ).call()
            return balance / (10 ** self.decimals)
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0.0
    
    def get_wallet_balance(self) -> float:
        """Get balance of the main wallet"""
        return self.get_usdt_balance(self.wallet_address)
    
    def check_for_deposits(self, user_address: str, amount: float, hours_back: int = 24) -> dict:
        """Check for deposits from a specific user"""
        try:
            url = f"{Config.BSC_SCAN_API}?module=account&action=tokentx&contractaddress={Config.USDT_CONTRACT}&address={self.wallet_address}&sort=desc&apikey={Config.BSC_SCAN_API_KEY}"
            
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data.get('status') != '1':
                logger.error(f"BSCScan API error: {data}")
                return {'success': False, 'error': 'Could not fetch transactions'}
            
            transactions = data.get('result', [])
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            deposits = []
            total_deposited = 0
            
            for tx in transactions:
                if tx.get('from', '').lower() != user_address.lower():
                    continue
                
                tx_time = datetime.fromtimestamp(int(tx.get('timeStamp', 0)))
                if tx_time < cutoff_time:
                    continue
                
                if tx.get('txreceipt_status') != '1':
                    continue
                
                if tx.get('to', '').lower() != self.wallet_address.lower():
                    continue
                
                amount_received = float(tx.get('value', 0)) / (10 ** self.decimals)
                if amount_received > 0:
                    deposits.append({
                        'amount': amount_received,
                        'tx_hash': tx.get('hash'),
                        'timestamp': tx_time,
                        'from': tx.get('from')
                    })
                    total_deposited += amount_received
            
            if deposits and total_deposited >= amount:
                return {
                    'success': True,
                    'total_amount': total_deposited,
                    'deposits': deposits,
                    'tx_hash': deposits[0]['tx_hash']
                }
            else:
                return {
                    'success': False, 
                    'error': f'No recent deposits found. Total found: {total_deposited}, Expected: {amount}'
                }
                
        except Exception as e:
            logger.error(f"Error checking deposits: {e}")
            return {'success': False, 'error': str(e)}
    
    def scan_all_deposits(self, last_block: int = None, hours_back: int = 1) -> list:
        """Scan for ALL new deposits to the main wallet"""
        try:
            if last_block:
                url = f"{Config.BSC_SCAN_API}?module=account&action=tokentx&contractaddress={Config.USDT_CONTRACT}&address={self.wallet_address}&startblock={last_block}&sort=asc&apikey={Config.BSC_SCAN_API_KEY}"
            else:
                url = f"{Config.BSC_SCAN_API}?module=account&action=tokentx&contractaddress={Config.USDT_CONTRACT}&address={self.wallet_address}&sort=desc&apikey={Config.BSC_SCAN_API_KEY}"
            
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data.get('status') != '1':
                logger.error(f"BSCScan API error: {data}")
                return []
            
            transactions = data.get('result', [])
            
            if not transactions:
                return []
            
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            deposits = []
            for tx in transactions:
                tx_time = datetime.fromtimestamp(int(tx.get('timeStamp', 0)))
                if tx_time < cutoff_time:
                    continue
                
                if tx.get('txreceipt_status') != '1':
                    continue
                
                if tx.get('to', '').lower() != self.wallet_address.lower():
                    continue
                
                amount = float(tx.get('value', 0)) / (10 ** self.decimals)
                if amount > 0:
                    deposits.append({
                        'from_address': tx.get('from'),
                        'amount': amount,
                        'tx_hash': tx.get('hash'),
                        'timestamp': tx_time,
                        'block_number': int(tx.get('blockNumber', 0))
                    })
            
            return deposits
            
        except Exception as e:
            logger.error(f"Error scanning deposits: {e}")
            return []
    
    def get_latest_block(self) -> int:
        """Get the latest block number from BSC"""
        try:
            return self.w3.eth.block_number
        except Exception as e:
            logger.error(f"Error getting latest block: {e}")
            return 0
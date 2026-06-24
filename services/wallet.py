from web3 import Web3
from config.settings import Config
import logging

logger = logging.getLogger(__name__)

class WalletService:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(Config.POLYGON_RPC_URL))
        self.project_wallet = Config.WALLET_ADDRESS
        self.usdt_contract = Config.USDT_CONTRACT
        self.usdt_decimals = Config.USDT_DECIMALS
        self.network = "Polygon"

    def verify_wallet(self, wallet_address):
        """Verify if wallet address is valid"""
        if not wallet_address or not wallet_address.startswith('0x') or len(wallet_address) != 42:
            return False, "Invalid wallet address format"

        if wallet_address.lower() == self.project_wallet.lower():
            return False, f"This is the project wallet on {self.network}. Please use your own."

        try:
            balance = self.w3.eth.get_balance(wallet_address)
            if balance > 0:
                return True, f"Wallet verified on {self.network}"
            token_balance = self.get_usdt_balance(wallet_address)
            if token_balance > 0:
                return True, f"Wallet verified on {self.network} (has USDT)"
            return True, f"Valid {self.network} wallet address"
        except Exception as e:
            logger.error(f"Error verifying wallet: {e}")
            return False, f"Could not verify wallet on {self.network}"

    def get_usdt_balance(self, wallet_address):
        """Get USDT balance on Polygon"""
        try:
            data = f"0x70a08231000000000000000000000000{wallet_address[2:].lower()}"
            result = self.w3.eth.call({
                'to': self.usdt_contract,
                'data': data
            })
            balance = int(result.hex(), 16) / 10**self.usdt_decimals
            return balance
        except Exception as e:
            logger.error(f"Error getting USDT balance: {e}")
            return 0

    def get_native_balance(self, wallet_address):
        """Get MATIC balance on Polygon"""
        try:
            balance = self.w3.eth.get_balance(wallet_address)
            return self.w3.from_wei(balance, 'ether')
        except Exception as e:
            logger.error(f"Error getting native balance: {e}")
            return 0

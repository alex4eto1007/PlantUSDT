import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # ============================================
    # TELEGRAM BOT
    # ============================================
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Alex_PlantUSDT")

    # ============================================
    # DATABASE
    # ============================================
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///plantusdt.db")

    # ============================================
    # POLYGON WALLET (Polygonscan API)
    # ============================================
    USDT_CONTRACT = os.getenv("USDT_CONTRACT", "0xc2132D05D31c914a87C6611C10748AEb04B58e8F")
    POLYGON_RPC_URL = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
    POLYGONSCAN_API_URL = os.getenv("POLYGONSCAN_API_URL", "https://api.polygonscan.com/api")
    POLYGON_CHAIN_ID = os.getenv("POLYGON_CHAIN_ID", "137")
    ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
    WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76")
    USDT_DECIMALS = int(os.getenv("USDT_DECIMALS", 6))

    # ============================================
    # INVESTMENT SETTINGS
    # ============================================
    DAILY_RATE = float(os.getenv("DAILY_RATE", 0.02))
    INVESTMENT_DAYS = int(os.getenv("INVESTMENT_DAYS", 30))
    MIN_INVESTMENT = float(os.getenv("MIN_INVESTMENT", 5))
    MAX_FIELD_AMOUNT = float(os.getenv("MAX_FIELD_AMOUNT", 100))

    # Updated multipliers: 1 day 2%, 7 days 15%, 30 days 65%
    LOCK_MULTIPLIERS = {
        1: 1.02,    # 2% return
        7: 1.15,    # 15% return (was 14%)
        30: 1.65    # 65% return (was 60%)
    }

    # ============================================
    # WITHDRAWAL SETTINGS
    # ============================================
    MIN_WITHDRAWAL = float(os.getenv("MIN_WITHDRAWAL", 2))
    WITHDRAWAL_FEE = float(os.getenv("WITHDRAWAL_FEE", 0.10))

    # ============================================
    # REFERRAL SETTINGS
    # ============================================
    REFERRAL_BONUS_PERCENT = float(os.getenv("REFERRAL_BONUS_PERCENT", 0.05))
    REFERRAL_WINDOW_SECONDS = int(os.getenv("REFERRAL_WINDOW_SECONDS", 180))

    # ============================================
    # APP URLS
    # ============================================
    VERCEL_URL = os.getenv("VERCEL_URL", "https://plant-usdt.vercel.app")
    API_BASE_URL = os.getenv("API_BASE_URL", "https://plantusdt.ddns.net")

    # ============================================
    # DEPOSIT SCANNER
    # ============================================
    SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", 300))
    BLOCK_CONFIRMATIONS = int(os.getenv("BLOCK_CONFIRMATIONS", 6))

    # ============================================
    # LOGGING
    # ============================================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "plantusdt.log")

    # ============================================
    # NETWORK INFO
    # ============================================
    NETWORK_NAME = "Polygon"
    NETWORK_SYMBOL = "MATIC"
    EXPLORER_URL = "https://polygonscan.com"

    @classmethod
    def get_network_info(cls):
        return {
            'name': cls.NETWORK_NAME,
            'symbol': cls.NETWORK_SYMBOL,
            'chain_id': cls.POLYGON_CHAIN_ID,
            'explorer': cls.EXPLORER_URL,
            'usdt_contract': cls.USDT_CONTRACT,
            'usdt_decimals': cls.USDT_DECIMALS
        }

    @classmethod
    def validate_config(cls):
        errors = []
        if not cls.BOT_TOKEN:
            errors.append("BOT_TOKEN is not set")
        if not cls.ETHERSCAN_API_KEY:
            errors.append("ETHERSCAN_API_KEY is not set")
        if not cls.WALLET_ADDRESS:
            errors.append("WALLET_ADDRESS is not set")
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is not set")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True

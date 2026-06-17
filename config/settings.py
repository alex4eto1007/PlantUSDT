import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "Admin")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///plantusdt.db")
    
    # Investment
    MIN_INVESTMENT = 5  # USDT
    DAILY_RATE = 0.02  # 2%
    INVESTMENT_DAYS = 30
    REFERRAL_BONUS = 0.05  # 5%
    MAX_FIELD_AMOUNT = 100  # Max USDT per field
    MAX_TOTAL_INVESTMENT = 300  # 3 fields × $100
    
    # Withdrawal
    MIN_WITHDRAWAL = 2  # USDT
    WITHDRAWAL_FEE = 0.10  # 10%
    
    # BSC Wallet
    USDT_CONTRACT = os.getenv("USDT_CONTRACT")
    BSC_RPC_URL = os.getenv("BSC_RPC_URL")
    BSC_SCAN_API = os.getenv("BSC_SCAN_API")
    BSC_SCAN_API_KEY = os.getenv("BSC_SCAN_API_KEY")
    WALLET_ADDRESS = os.getenv("WALLET_ADDRESS")
    CHAIN_ID = 56
    
    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
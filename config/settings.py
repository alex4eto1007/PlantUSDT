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
    # BSC WALLET (Etherscan V2 API)
    # ============================================
    USDT_CONTRACT = os.getenv("USDT_CONTRACT", "0x55d398326f99059fF775485246999027B3197955")
    BSC_RPC_URL = os.getenv("BSC_RPC_URL", "https://bsc-dataseed.binance.org/")
    BSC_SCAN_API = os.getenv("BSC_SCAN_API", "https://api.etherscan.io/v2/api")
    BSC_SCAN_CHAIN_ID = os.getenv("BSC_SCAN_CHAIN_ID", "56")  # BSC mainnet
    BSC_SCAN_API_KEY = os.getenv("BSC_SCAN_API_KEY")
    WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76")

    # ============================================
    # INVESTMENT SETTINGS
    # ============================================
    DAILY_RATE = float(os.getenv("DAILY_RATE", 0.02))
    INVESTMENT_DAYS = int(os.getenv("INVESTMENT_DAYS", 30))
    MIN_INVESTMENT = float(os.getenv("MIN_INVESTMENT", 5))
    MAX_FIELD_AMOUNT = float(os.getenv("MAX_FIELD_AMOUNT", 100))

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

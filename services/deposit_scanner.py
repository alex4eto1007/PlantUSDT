# ============================================
# PLANTUSDT - ENVIRONMENT VARIABLES
# ============================================

# Telegram Bot Configuration
BOT_TOKEN=YOUR_BOT_TOKEN_HERE

# Admin User IDs (comma separated)
ADMIN_IDS=6988485148
ADMIN_USERNAME=Alex_PlantUSDT

# ============================================
# DATABASE CONFIGURATION
# ============================================

DATABASE_URL=postgresql://plantusdt_user:YOUR_PASSWORD@localhost/plantusdt

# ============================================
# POLYGON BLOCKCHAIN CONFIGURATION - V2 API
# ============================================

# V2 API URL (Etherscan V2 with chainid parameter)
POLYGONSCAN_API_URL=https://api.etherscan.io/v2/api?chainid=137

# Polygon Chain ID (137 for mainnet)
POLYGON_CHAIN_ID=137

# Your Etherscan API Key (works for Polygonscan too!)
ETHERSCAN_API_KEY=YOUR_API_KEY_HERE

# Project Wallet (Polygon USDT)
WALLET_ADDRESS=0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76

# USDT Contract Address on Polygon (ERC-20)
USDT_CONTRACT=0xc2132D05D31c914a87C6611C10748AEb04B58e8F

# Polygon Network RPC
POLYGON_RPC_URL=https://polygon-rpc.com

# USDT Decimals on Polygon (6, not 18!)
USDT_DECIMALS=6

# ============================================
# NETWORK INFO
# ============================================

NETWORK_NAME=Polygon
NETWORK_SYMBOL=MATIC
EXPLORER_URL=https://polygonscan.com

# ============================================
# INVESTMENT CONFIGURATION
# ============================================

DAILY_RATE=0.02
INVESTMENT_DAYS=30
MAX_FIELD_AMOUNT=100
MIN_INVESTMENT=5

# ============================================
# WITHDRAWAL CONFIGURATION
# ============================================

MIN_WITHDRAWAL=2
WITHDRAWAL_FEE=0.10

# ============================================
# REFERRAL CONFIGURATION
# ============================================

REFERRAL_BONUS_PERCENT=0.01
REFERRAL_WINDOW_SECONDS=180

# ============================================
# MINI APP CONFIGURATION
# ============================================

VERCEL_URL=https://plant-usdt.vercel.app
API_BASE_URL=https://plantusdt.ddns.net

# ============================================
# DEPOSIT SCANNER CONFIGURATION
# ============================================

SCAN_INTERVAL_SECONDS=300
BLOCK_CONFIRMATIONS=6

# ============================================
# LOGGING CONFIGURATION
# ============================================

LOG_LEVEL=INFO
LOG_FILE=plantusdt.log

import logging
from telegram import Update
from telegram.ext import ContextTypes
from database.db_manager import DatabaseManager
from config.settings import Config

logger = logging.getLogger(__name__)
db = DatabaseManager()

async def set_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set withdrawal wallet address"""
    user = update.effective_user
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "❌ Please provide your Polygon wallet address.\n\n"
            "Example: /setwallet 0xYourPolygonAddress\n\n"
            "Please use /setwallet 0xYourPolygonAddress to set your withdrawal address."
        )
        return
    
    wallet_address = args[0]
    
    if not wallet_address.startswith('0x') or len(wallet_address) != 42:
        await update.message.reply_text(
            "❌ Invalid wallet address. Please enter a valid Polygon wallet address (0x...)."
        )
        return
    
    # Block project wallet
    if wallet_address.lower() == Config.WALLET_ADDRESS.lower():
        await update.message.reply_text(
            "❌ This is the project wallet. Please enter your own Polygon wallet address."
        )
        return
    
    success = db.update_user_wallet(user.id, wallet_address)
    
    if success:
        await update.message.reply_text(
            f"✅ Withdrawal wallet set successfully!\n\n"
            f"📍 Address: {wallet_address[:6]}...{wallet_address[-4:]}\n"
            f"⛓️ Network: Polygon"
        )
    else:
        await update.message.reply_text(
            "❌ Failed to set wallet. Please try again."
        )

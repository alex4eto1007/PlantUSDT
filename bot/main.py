from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config.settings import Config
from database.db_manager import DatabaseManager
from services.investment import InvestmentService
from services.wallet import WalletService
from services.deposit_scanner import DepositScanner
from services.scheduler import SchedulerService
import logging
import asyncio

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Initialize services
db = DatabaseManager()
investment_service = InvestmentService()
wallet_service = WalletService()
scheduler = SchedulerService()
deposit_scanner = DepositScanner()

# Create tables
db.create_tables()

# Vercel URL for Mini App
VERCEL_URL = "https://plant-usdt.vercel.app"

# Admin check function
def is_admin(user_id: int) -> bool:
    user = db.get_user(user_id)
    return user and user.is_admin

# ============================================
# START COMMAND - WITH REFERRAL HANDLING
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    existing_user = db.get_user(user.id)
    if not existing_user:
        referred_by = None
        if context.args and len(context.args) > 0:
            referral_code = context.args[0]
            referrer = db.get_user_by_referral_code(referral_code)
            if referrer:
                referred_by = referrer.id
                logger.info(f"User {user.id} referred by {referrer.telegram_id}")
        
        db.create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            referred_by=referred_by
        )
        
        welcome_text = f"""🌱 Welcome to PlantUSDT, {user.first_name}!

Grow your USDT with 2% DAILY returns for 30 days!

💰 INVESTMENT DETAILS:
• 📈 Daily return: 2%
• ⏱️ Duration: 30 days  
• 💰 Minimum deposit: $5 USDT
• 🏦 Minimum withdrawal: $2 USDT
• 🔒 Platform fee: 10% on withdrawals
• 🌱 3 Planting Fields: $100 max each

👥 REFERRAL BONUS:
Share your referral link and earn 5% from your friends' deposits!

Use /app to open the Mini App!"""
        
        keyboard = [
            [InlineKeyboardButton("🌱 Open PlantUSDT App", web_app=WebAppInfo(url=VERCEL_URL))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    else:
        keyboard = [
            [InlineKeyboardButton("🌱 Open PlantUSDT App", web_app=WebAppInfo(url=VERCEL_URL))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Welcome back, {user.first_name}! 🌱\n\nOpen the PlantUSDT App below:",
            reply_markup=reply_markup
        )

# ============================================
# APP COMMAND
# ============================================

async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("🌱 Open PlantUSDT App", web_app=WebAppInfo(url=VERCEL_URL))
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("🌱 Open the PlantUSDT Mini App:", reply_markup=reply_markup)

# ============================================
# ADMIN COMMANDS
# ============================================

async def pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    pending = db.get_pending_withdrawals()
    
    if not pending:
        await update.message.reply_text("📋 No pending withdrawals.")
        return
    
    text = "📋 PENDING WITHDRAWALS\n\n"
    for w in pending:
        user_obj = db.get_user_by_id(w.user_id)
        username = user_obj.username if user_obj else "Unknown"
        text += f"ID: {w.id}\n"
        text += f"👤 User: @{username}\n"
        text += f"💰 Amount: ${w.amount:.2f} USDT\n"
        text += f"🔒 Fee (10%): ${w.fee:.2f} USDT\n"
        text += f"💵 Net: ${w.net_amount:.2f} USDT\n"
        text += f"🏦 Wallet: {w.wallet_address[:10]}...{w.wallet_address[-8:]}\n"
        text += f"📅 Requested: {w.created_at.strftime('%d/%m/%Y %H:%M')}\n"
        text += f"Status: ⏳ Pending\n"
        text += f"To complete: /complete_payout {w.id} TX_HASH\n\n"
    
    await update.message.reply_text(text)

async def complete_payout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: /complete_payout <withdrawal_id> <tx_hash>\n\n"
            "Example: /complete_payout 1 0xabc123..."
        )
        return
    
    try:
        withdrawal_id = int(context.args[0])
        tx_hash = context.args[1]
    except ValueError:
        await update.message.reply_text("❌ Invalid withdrawal ID. Please provide a valid number.")
        return
    
    withdrawal = db.get_withdrawal_by_id(withdrawal_id)
    if not withdrawal:
        await update.message.reply_text(f"❌ Withdrawal ID {withdrawal_id} not found.")
        return
    
    if withdrawal.status != "pending":
        await update.message.reply_text(f"❌ Withdrawal {withdrawal_id} is already {withdrawal.status}.")
        return
    
    updated = db.update_withdrawal_status(withdrawal_id, "completed", tx_hash)
    if updated:
        await update.message.reply_text(
            f"✅ Withdrawal {withdrawal_id} marked as COMPLETED!\n\n"
            f"💰 Amount: ${withdrawal.amount:.2f} USDT\n"
            f"💵 Net: ${withdrawal.net_amount:.2f} USDT\n"
            f"🔗 TX: {tx_hash}"
        )
        
        user_obj = db.get_user_by_id(withdrawal.user_id)
        if user_obj:
            try:
                await context.bot.send_message(
                    chat_id=user_obj.telegram_id,
                    text=f"✅ Your withdrawal request has been processed!\n\n"
                         f"💰 Amount: ${withdrawal.amount:.2f} USDT\n"
                         f"💵 Net: ${withdrawal.net_amount:.2f} USDT\n"
                         f"🔗 TX: {tx_hash}\n\n"
                         f"Check your wallet!"
                )
            except Exception as e:
                logger.error(f"Error notifying user: {e}")
    else:
        await update.message.reply_text(f"❌ Failed to update withdrawal {withdrawal_id}.")

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    help_text = """👑 ADMIN COMMANDS

/pending - View all pending withdrawals
/complete_payout <id> <tx_hash> - Mark a payout as completed

Example:
/pending
/complete_payout 1 0xabc123...

💡 The transaction hash should be from sending USDT on BEP-20 (BSC) network."""
    
    await update.message.reply_text(help_text)

# ============================================
# MAIN FUNCTION
# ============================================

def main():
    """Start the bot"""
    try:
        # Start scheduler
        scheduler.start()
        
        application = Application.builder().token(Config.BOT_TOKEN).build()
        
        # User commands
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("app", app_command))
        
        # Admin commands
        application.add_handler(CommandHandler("pending", pending_withdrawals))
        application.add_handler(CommandHandler("complete_payout", complete_payout))
        application.add_handler(CommandHandler("adminhelp", admin_help))
        
        # Start deposit scanner in background
        async def start_deposit_scanner():
            while True:
                try:
                    await deposit_scanner.scan_for_deposits(application.bot)
                except Exception as e:
                    logger.error(f"Error in deposit scanner loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes
        
        # Run the scanner in background
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(start_deposit_scanner())
        
        logger.info("🌱 PlantUSDT Bot started! Press Ctrl+C to stop.")
        logger.info(f"📱 Mini App URL: {VERCEL_URL}")
        logger.info("🔍 Deposit scanner running (checks every 5 minutes)")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    main()

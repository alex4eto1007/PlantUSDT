from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config.settings import Config
from database.db_manager import DatabaseManager
from database.models import User
from services.investment import InvestmentService
from services.wallet import WalletService
from services.deposit_scanner import DepositScanner
from services.scheduler import SchedulerService
import logging
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================
# RATE LIMITING
# ============================================
user_requests = defaultdict(list)

def check_rate_limit(user_id: int, limit: int = 10, period: int = 60) -> bool:
    """Check if user has exceeded rate limit (10 requests per 60 seconds)"""
    now = datetime.utcnow()
    user_requests[user_id] = [t for t in user_requests[user_id] if (now - t).seconds < period]
    if len(user_requests[user_id]) >= limit:
        return False
    user_requests[user_id].append(now)
    return True

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Global application variable (for importing in other modules)
application = None

# Initialize services
db = DatabaseManager()
investment_service = InvestmentService()
wallet_service = WalletService()
scheduler = SchedulerService()
deposit_scanner = DepositScanner()

# Create tables
db.create_tables()

# Vercel URL for Mini App with cache-busting
VERCEL_URL = "https://plant-usdt.vercel.app?v=5"

# Admin check function
def is_admin(user_id: int) -> bool:
    user = db.get_user(user_id)
    return user and user.is_admin

# ============================================
# START COMMAND - WITH REFERRAL HANDLING
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Rate limiting
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    now = datetime.utcnow()

    logger.info(f"START COMMAND - User: {user.id}, Args: {context.args}")

    existing_user = db.get_user(user.id)

    if not existing_user:
        # NEW USER - Create account with referral
        referred_by = None
        if context.args and len(context.args) > 0:
            referral_code = context.args[0]
            logger.info(f"New user - Referral code received: {referral_code}")
            referrer = db.get_user_by_referral_code(referral_code)
            if referrer:
                referred_by = referrer.id
                logger.info(f"New user {user.id} referred by {referrer.telegram_id}")
            else:
                logger.info(f"Referral code {referral_code} not found")

        db.create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            referred_by=referred_by
        )

        welcome_text = f"""🌱 Welcome to PlantUSDT, {user.first_name}!

Grow your USDT with returns up to 65% on Polygon network!

💰 INVESTMENT DETAILS:
• 🌿 1 Day: 2% return
• 🌿 7 Days: 15% return  
• 🌿 30 Days: 65% return
• 💰 Minimum deposit: $5 USDT
• 🏦 Minimum withdrawal: $2 USDT
• 🔒 Platform fee: 10% on withdrawals
• 🌱 3 Planting Fields: $100 max each
• ⛓️ Network: Polygon (MATIC) - Low fees!

👥 REFERRAL BONUS:
Share your referral link and earn 5% from your friends' deposits!

📋 COMMANDS:
/start - Start the bot
/app - Open Mini App
/help - Show all commands
/balance - Check your balance
/status - Check your investments
/support - Contact support

💡 Open the Mini App for full features!
   - Deposit USDT
   - Invest in fields
   - Track earnings
   - Refer friends

🔗 Mini App: https://plant-usdt.vercel.app"""

        keyboard = [
            [InlineKeyboardButton("🌱 Open PlantUSDT", web_app=WebAppInfo(url=VERCEL_URL))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        return

    # ============================================
    # EXISTING USER - Check if they can accept a referral
    # 3-MINUTE WINDOW
    # ============================================
    if context.args and len(context.args) > 0 and existing_user.can_be_referred and existing_user.referred_by is None:
        referral_code = context.args[0]
        logger.info(f"Existing user {user.id} trying to accept referral: {referral_code}")

        # Check if user is within 3-minute window
        seconds_since_creation = (now - existing_user.created_at).total_seconds()

        if seconds_since_creation <= 180:  # 3 minutes = 180 seconds
            referrer = db.get_user_by_referral_code(referral_code)
            if referrer and referrer.id != existing_user.id:
                # Check if referrer is trying to refer themselves
                if referrer.id == existing_user.id:
                    await update.message.reply_text("❌ You cannot refer yourself!")
                    return

                # ============================================
                # APPLY REFERRAL - NO BONUS
                # ============================================
                session = db.get_session()

                # Get fresh user objects in this session
                user_obj = session.query(User).filter_by(telegram_id=user.id).first()
                referrer_obj = session.query(User).filter_by(id=referrer.id).first()

                if user_obj and referrer_obj:
                    user_obj.referred_by = referrer.id
                    user_obj.referred_at = now
                    user_obj.can_be_referred = False

                    session.commit()
                    logger.info(f"Referral saved: {user.id} referred by {referrer.id}")
                else:
                    logger.error(f"Could not find user or referrer in session")
                    session.rollback()

                await update.message.reply_text(
                    f"✅ You have been successfully referred by @{referrer_obj.username or 'User'}! 🎉\n\n"
                    f"Welcome to the PlantUSDT community! 🌱\n\n"
                    f"💡 Your referrer will earn 5% from your future deposits!"
                )

                # Notify referrer
                try:
                    await context.bot.send_message(
                        chat_id=referrer.telegram_id,
                        text=f"🎉 **New Referral!**\n\n"
                             f"@{existing_user.username or 'User'} accepted your referral!\n"
                             f"💡 You will earn 5% from their future deposits!\n"
                             f"⛓️ Network: Polygon"
                    )
                except Exception as e:
                    logger.error(f"Error notifying referrer: {e}")

                return
            else:
                await update.message.reply_text("❌ Invalid referral code or referrer not found.")
                return
        else:
            await update.message.reply_text(
                f"❌ Sorry, you can only accept a referral within 3 minutes of creating your account.\n\n"
                f"Your account was created on {existing_user.created_at.strftime('%d/%m/%Y %H:%M:%S')} UTC.\n"
                f"You are {int(seconds_since_creation)} seconds old.\n"
                f"The referral window is only 3 minutes."
            )
            return

    # Regular welcome back message
    keyboard = [
        [InlineKeyboardButton("🌱 Open PlantUSDT", web_app=WebAppInfo(url=VERCEL_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Welcome back, {user.first_name}! 🌱\n\nOpen the PlantUSDT App below:",
        reply_markup=reply_markup
    )

# ============================================
# APP COMMAND - Direct Mini App Link
# ============================================

async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    keyboard = [[
        InlineKeyboardButton("🌱 Open PlantUSDT", web_app=WebAppInfo(url=VERCEL_URL))
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🌱 **Open PlantUSDT Mini App**\n\n"
        "Click the button below to:\n"
        "💰 Check your balance\n"
        "🌾 Invest in planting fields\n"
        "📊 View your earnings\n"
        "👥 Manage referrals\n\n"
        "Start growing your USDT today on Polygon! 🚀",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ============================================
# INTERACTIVE COMMANDS (for Adsgram approval)
# ============================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return

    help_text = """🌱 **PlantUSDT Help**

Commands:
/start - Start the bot
/app - Open Mini App
/help - Show this help
/balance - Check your balance
/status - Check your investments
/support - Contact support

💡 Open the Mini App for full features!
   - Deposit USDT
   - Invest in fields
   - Track earnings
   - Refer friends

🔗 Mini App: https://plant-usdt.vercel.app"""

    await update.message.reply_text(help_text, parse_mode='Markdown')

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return

    user_data = db.get_user(user.id)
    if user_data:
        # Check if user has any active investments
        investments = db.get_active_investments_by_user(user_data.id)
        locked_amount = sum(inv.amount for inv in investments)
        
        await update.message.reply_text(
            f"💰 **Your Balance**\n\n"
            f"Available: **${user_data.balance:.2f}** USDT\n"
            f"Locked in investments: **${locked_amount:.2f}** USDT\n"
            f"Total deposited: **${user_data.total_deposited:.2f}** USDT\n"
            f"Total earned: **${user_data.total_earned:.2f}** USDT\n"
            f"⛓️ Network: Polygon"
        )
    else:
        await update.message.reply_text("❌ User not found. Please /start first.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return

    user_data = db.get_user(user.id)
    if not user_data:
        await update.message.reply_text("❌ User not found. Please /start first.")
        return
    
    investments = db.get_active_investments_by_user(user_data.id)
    if not investments:
        await update.message.reply_text("🌱 You have no active investments.")
        return
    
    text = "📊 **Your Active Investments**\n\n"
    for inv in investments:
        text += f"🌾 Field #{inv.field_number}: **${inv.amount:.2f}** USDT (Locked)\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return

    await update.message.reply_text(
        "📧 **Contact Support**\n\n"
        "For help, contact: @Alex_PlantUSDT\n\n"
        "Or open the Mini App and use the support feature.\n\n"
        "💡 If you have issues with deposits, please include your transaction hash."
    )

# ============================================
# ADMIN COMMANDS
# ============================================

async def pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
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
        text += f"🏦 Wallet: <code>{w.wallet_address}</code>\n"
        text += f"📅 Requested: {w.created_at.strftime('%d/%m/%Y %H:%M')}\n"
        text += f"Status: ⏳ Pending\n"
        text += f"To complete: /complete_payout {w.id} TX_HASH\n\n"

    await update.message.reply_text(text, parse_mode='HTML')

async def complete_payout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: /complete_payout <withdrawal_id> <tx_hash>\n\n"
            "Example: /complete_payout 1 0xabc123...\n\n"
            "💡 Transaction hash should be from sending USDT on Polygon network."
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
            f"🔗 TX: {tx_hash}\n"
            f"⛓️ Network: Polygon"
        )

        user_obj = db.get_user_by_id(withdrawal.user_id)
        if user_obj:
            try:
                await context.bot.send_message(
                    chat_id=user_obj.telegram_id,
                    text=f"✅ Your withdrawal request has been processed!\n\n"
                         f"💰 Amount: ${withdrawal.amount:.2f} USDT\n"
                         f"💵 Net: ${withdrawal.net_amount:.2f} USDT\n"
                         f"🔗 TX: {tx_hash}\n"
                         f"⛓️ Network: Polygon\n\n"
                         f"Check your wallet!"
                )
            except Exception as e:
                logger.error(f"Error notifying user: {e}")
    else:
        await update.message.reply_text(f"❌ Failed to update withdrawal {withdrawal_id}.")

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    help_text = """👑 ADMIN COMMANDS

/pending - View all pending withdrawals
/complete_payout <id> <tx_hash> - Mark a payout as completed
/reset_referral <user_id> - Reset a user's referral status

Example:
/pending
/complete_payout 1 0xabc123...
/reset_referral 123456789

💡 Transactions are on Polygon (MATIC) network using USDT on Polygon"""

    await update.message.reply_text(help_text)

async def reset_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ Usage: /reset_referral <user_id>\n\n"
            "Example: /reset_referral 123456789\n\n"
            "This will allow the user to accept a new referral."
        )
        return

    try:
        target_user_id = int(context.args[0])
        target_user = db.get_user(target_user_id)

        if not target_user:
            await update.message.reply_text(f"❌ User {target_user_id} not found.")
            return

        db.reset_user_referral(target_user.id)

        await update.message.reply_text(
            f"✅ Referral reset for @{target_user.username or 'User'}!\n\n"
            f"They can now accept a new referral."
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

# ============================================
# MAIN FUNCTION
# ============================================

def main():
    """Start the bot"""
    global application
    try:
        # Start scheduler
        scheduler.start()

        application = Application.builder().token(Config.BOT_TOKEN).build()

        # User commands
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("app", app_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("support", support_command))

        # Admin commands
        application.add_handler(CommandHandler("pending", pending_withdrawals))
        application.add_handler(CommandHandler("complete_payout", complete_payout))
        application.add_handler(CommandHandler("adminhelp", admin_help))
        application.add_handler(CommandHandler("reset_referral", reset_referral))

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

        # Set persistent menu button
        async def set_menu_button():
            try:
                await application.bot.set_chat_menu_button(
                    chat_id=None,
                    menu_button={
                        "type": "web_app",
                        "text": "🌱 PlantUSDT",
                        "web_app": {"url": VERCEL_URL}
                    }
                )
                logger.info("✅ Menu button set to Mini App")
            except Exception as e:
                logger.error(f"❌ Error setting menu button: {e}")

        loop.create_task(set_menu_button())

        logger.info("🌱 PlantUSDT Bot started! Press Ctrl+C to stop.")
        logger.info(f"📱 Mini App URL: {VERCEL_URL}")
        logger.info("🔍 Deposit scanner running on Polygon (checks every 5 minutes)")
        logger.info("📌 Menu button set to: 🌱 PlantUSDT")

        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    main()

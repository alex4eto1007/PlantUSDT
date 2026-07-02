from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config.settings import Config
from database.db_manager import DatabaseManager
from database.models import User, Investment, Withdrawal, Deposit
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

application = None

db = DatabaseManager()
investment_service = InvestmentService()
wallet_service = WalletService()
scheduler = SchedulerService()
deposit_scanner = DepositScanner()

db.create_tables()

VERCEL_URL = "https://plant-usdt.vercel.app?v=6"
PROJECT_WALLET = '0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76'

# ============================================
# CHANNEL FOR TRANSACTION UPDATES
# ============================================
CHANNEL_ID = -1004391112772  # @PlantUSDTtransactions

async def send_to_channel(bot, message: str):
    """Send a message to the transaction channel"""
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=message,
            parse_mode='Markdown'
        )
        logger.info("✅ Transaction update sent to channel")
    except Exception as e:
        logger.error(f"❌ Failed to send to channel: {e}")

# ============================================
# COMMUNITY FOOTER
# ============================================

def get_community_footer():
    """Return the community footer with channel and group links"""
    return (
        "\n\n━━━━━━━━━━━━━━━━━━━━\n"
        "🌱 **Join our community!**\n"
        "📢 Channel: [PlantUSDTchannel](https://t.me/PlantUSDTchannel)\n"
        "💬 Group: [PlantUSDT](https://t.me/PlantUSDT)\n"
        "📊 Transactions: [PlantUSDTtransactions](https://t.me/PlantUSDTtransactions)\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

def is_admin(user_id: int) -> bool:
    user = db.get_user(user_id)
    return user and user.is_admin

# ============================================
# START COMMAND
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    now = datetime.utcnow()
    existing_user = db.get_user(user.id)

    if not existing_user:
        referred_by = None
        if context.args and len(context.args) > 0:
            referral_code = context.args[0]
            referrer = db.get_user_by_referral_code(referral_code)
            if referrer:
                referred_by = referrer.id
        db.create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            referred_by=referred_by
        )
        welcome_text = f"""🌱 Welcome to PlantUSDT, {user.first_name}!

Grow your USDT with returns up to 80% on Polygon network!

💰 INVESTMENT DETAILS:
• 🌿 1 Day: 2% return
• 🌿 7 Days: 18% return  
• 🌿 30 Days: 80% return
• 💰 Minimum deposit: $5 USDT
• 🏦 Minimum withdrawal: $2 USDT
• 🔒 Platform fee: 10% on withdrawals
• 🌱 3 Planting Fields: $100 max each
• ⛓️ Network: Polygon (MATIC) - Low fees!

👥 REFERRAL BONUS:
Share your referral link and earn 1% from your friends' deposits!

📊 Live Transactions: @PlantUSDTtransactions

Use /app to open the Mini App!"""
        keyboard = [[InlineKeyboardButton("🌱 Open PlantUSDT", web_app=WebAppInfo(url=VERCEL_URL))]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            welcome_text + get_community_footer(),
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return

    # Referral handling – only for new users, silently ignore existing
    if context.args and len(context.args) > 0:
        referral_code = context.args[0]
        if existing_user.can_be_referred and existing_user.referred_by is None:
            seconds_since_creation = (now - existing_user.created_at).total_seconds()
            if seconds_since_creation <= 180:
                referrer = db.get_user_by_referral_code(referral_code)
                if referrer and referrer.id != existing_user.id:
                    session = db.get_session()
                    user_obj = session.query(User).filter_by(telegram_id=user.id).first()
                    referrer_obj = session.query(User).filter_by(id=referrer.id).first()
                    if user_obj and referrer_obj:
                        user_obj.referred_by = referrer.id
                        user_obj.referred_at = now
                        user_obj.can_be_referred = False
                        session.commit()
                        await update.message.reply_text(
                            f"✅ You have been successfully referred by @{referrer_obj.username or 'User'}! 🎉\n\n"
                            f"Welcome to the PlantUSDT community! 🌱\n\n"
                            f"💡 Your referrer will earn 1% from your future deposits!"
                            + get_community_footer(),
                            parse_mode='Markdown'
                        )
                        try:
                            await context.bot.send_message(
                                chat_id=referrer.telegram_id,
                                text=f"🎉 **New Referral!**\n\n"
                                     f"@{existing_user.username or 'User'} accepted your referral!\n"
                                     f"💡 You will earn 1% from their future deposits!"
                                     + get_community_footer(),
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Error notifying referrer: {e}")
                        session.close()
                        return
                    session.close()

    keyboard = [[InlineKeyboardButton("🌱 Open PlantUSDT", web_app=WebAppInfo(url=VERCEL_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"Welcome back, {user.first_name}! 🌱\n\nOpen the PlantUSDT App below:"
        + get_community_footer(),
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ============================================
# APP COMMAND
# ============================================

async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    keyboard = [[InlineKeyboardButton("🌱 Open PlantUSDT", web_app=WebAppInfo(url=VERCEL_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🌱 **Open PlantUSDT Mini App**\n\n"
        "Click the button below to:\n"
        "💰 Check your balance\n"
        "🌾 Invest in planting fields\n"
        "📊 View your earnings\n"
        "👥 Manage referrals\n\n"
        "Start growing your USDT today on Polygon! 🚀"
        + get_community_footer(),
        reply_markup=reply_markup,
        parse_mode='Markdown'
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
        await update.message.reply_text(
            "📋 No pending withdrawals." + get_community_footer(),
            parse_mode='Markdown'
        )
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

    await update.message.reply_text(
        text + get_community_footer(),
        parse_mode='HTML'
    )

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
            + get_community_footer(),
            parse_mode='Markdown'
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
            + get_community_footer(),
            parse_mode='Markdown'
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
                         + get_community_footer(),
                    parse_mode='Markdown'
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

    await update.message.reply_text(
        help_text + get_community_footer(),
        parse_mode='Markdown'
    )

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
            + get_community_footer(),
            parse_mode='Markdown'
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
            + get_community_footer(),
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

# ============================================
# ADMIN CHECK
# ============================================

def is_admin(user_id: int) -> bool:
    user = db.get_user(user_id)
    return user and user.is_admin

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
        logger.info("📢 Community footer added to all messages")
        logger.info("📊 Transaction channel: @PlantUSDTtransactions")

        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    main()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from config.settings import Config
from database.db_manager import DatabaseManager
from database.models import User, Investment, Withdrawal, Deposit, UncollectedFee, AuditLog
from services.investment import InvestmentService
from services.wallet import WalletService
from services.deposit_scanner import DepositScanner
from services.scheduler import SchedulerService
from services.referral import upgrade_referral_tier, get_referral_stats, REFERRAL_TIERS
from services.task_manager import (
    create_task, get_all_tasks, get_user_tasks,
    complete_task, claim_task_reward, delete_task
)
import logging
import asyncio
import json
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal

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

VERCEL_URL = "https://plant-usdt.vercel.app?cb=20260738"
PROJECT_WALLET = '0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76'

# ============================================
# CHANNEL FOR TRANSACTION UPDATES
# ============================================
CHANNEL_ID = -1004391112772

async def send_to_channel(bot, message: str):
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

    # ============================================
    # UPDATE USER INFO (NAME & USERNAME) ON EVERY START
    # ============================================
    db.update_user_info(user.id, user.username, user.first_name)

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

💰 **INVESTMENT DETAILS:**
• 🌿 1 Day: 2% return
• 🌿 7 Days: 18% return
• 🌿 30 Days: 80% return
• 💰 Minimum deposit: $5 USDT
• 🏦 Minimum withdrawal: $1 USDT
• 🔒 Platform fee: 5% on withdrawals
• 🌱 3 Planting Fields: $100 max each
• ⛓️ Network: Polygon (MATIC) - Low fees!

👥 **REFERRAL BONUS:**
Share your referral link and earn up to 5% from your friends' deposits based on your tier!

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

    # Existing user - handle referral first
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
                            f"💡 Your referrer will earn from your future deposits based on their referral tier!"
                            + get_community_footer(),
                            parse_mode='Markdown'
                        )
                        try:
                            await context.bot.send_message(
                                chat_id=referrer.telegram_id,
                                text=f"🎉 **New Referral!**\n\n"
                                     f"@{existing_user.username or 'User'} accepted your referral!\n"
                                     f"💡 You will earn from their future deposits based on your tier!"
                                     + get_community_footer(),
                                parse_mode='Markdown'
                            )
                        except Exception as e:
                            logger.error(f"Error notifying referrer: {e}")
                        session.close()
                        return
                    session.close()

    # Send the welcome back message
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
    
    # Update user info on /app command too
    db.update_user_info(user.id, user.username, user.first_name)
    
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
# BALANCE COMMAND
# ============================================

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's balance"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    session = db.get_session()
    user_data = session.query(User).filter_by(telegram_id=user.id).first()
    session.close()
    
    if not user_data:
        await update.message.reply_text("❌ User not found. Please use /start first.")
        return
    
    balance = user_data.balance or 0
    user_id = user.id

    await update.message.reply_text(
        f"👛 Your Balance\n\n"
        f"🆔 User ID: {user_id}\n"
        f"💵 {balance:.2f} USDT"
    )

# ============================================
# REFERRALS COMMAND
# ============================================

async def referrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's referrals"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    session = db.get_session()
    user_data = session.query(User).filter_by(telegram_id=user.id).first()
    session.close()
    
    if not user_data:
        await update.message.reply_text("❌ User not found. Please use /start first.")
        return
    
    referral_count = session.query(User).filter_by(referred_by=user_data.id).count()
    active_count = user_data.total_active_referrals or 0
    referral_earnings = user_data.referral_earnings_all_time or 0
    referral_code = user_data.referral_code
    referral_link = f"https://t.me/PlantUSDT_bot?start={referral_code}"
    
    keyboard = [
        [InlineKeyboardButton("📤 Share Link", callback_data=f"share_referral_{referral_code}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👥 **Your Referrals**\n\n"
        f"Total: **{referral_count}**\n"
        f"Active: **{active_count}**\n"
        f"Earned: **${referral_earnings:.2f}**\n\n"
        f"🔗 `{referral_link}`",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ============================================
# WITHDRAW COMMAND
# ============================================

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show withdrawal information"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    keyboard = [
        [InlineKeyboardButton("💲 Withdraw now", web_app=WebAppInfo(url=VERCEL_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🏦 **Withdraw**\n\n"
        f"Withdraw your USDT on Polygon network 🟣\n\n"
        f"⛓️ **Network:** Polygon\n"
        f"💵 **Token:** USDT\n"
        f"💰 **Min withdrawal:** $1.00\n"
        f"💸 **Fees:** 15% — 25% (based on amount)\n\n"
        f"**Amount breakdown:**\n"
        f"• $1 — $49.99 → 15% fee\n"
        f"• $50 — $99.99 → 20% fee\n"
        f"• $100+ → 25% fee",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ============================================
# SHARE REFERRAL CALLBACK
# ============================================

async def share_referral_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle share referral button press"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    referral_code = data.replace("share_referral_", "")
    referral_link = f"https://t.me/PlantUSDT_bot?start={referral_code}"
    
    try:
        await query.message.reply_text(
            f"📤 **Share your referral link!**\n\n"
            f"Send this link to your friends:\n\n"
            f"`{referral_link}`\n\n"
            f"Use the forward button below to share it! 📤",
            parse_mode='Markdown'
        )
        await query.edit_message_text(
            f"✅ Link copied! Share it with your friends:\n\n"
            f"`{referral_link}`",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sharing referral: {e}")
        await query.edit_message_text(
            f"📤 **Share your referral link**\n\n"
            f"Copy this link and send it to your friends:\n\n"
            f"`{referral_link}`",
            parse_mode='Markdown'
        )

# ============================================
# WEB APP DATA HANDLER
# ============================================

async def handle_web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle data sent from the Mini App via tg.sendData()"""
    try:
        data = json.loads(update.message.web_app_data.data)
        logger.info(f"📩 WebApp data received: {data}")
        
        data_type = data.get('type')
        user = update.effective_user
        
        if data_type == 'share_referral':
            link = data.get('link')
            
            message = (
                f"🌱 **Share this referral link with your friends!**\n\n"
                f"{link}\n\n"
                f"💰 Earn up to 5% of their deposits based on your tier!\n"
                f"👥 Your current bonus: Check your tier in the Mini App.\n\n"
                f"📊 Live Transactions: @PlantUSDTtransactions"
            )
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown'
            )
            logger.info(f"📤 Referral link shared by user {user.id}")
            
        else:
            logger.info(f"Unknown web_app_data type: {data_type}")
            
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse web_app_data: {e}")
    except Exception as e:
        logger.error(f"Error handling web_app_data: {e}")

# ============================================
# RESET MENU ALL COMMAND
# ============================================

async def reset_menu_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset menu button for ALL users (admin only)"""
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ Not authorized.")
        return
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, reset for all", callback_data="reset_menu_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="reset_menu_cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚠️ This will reset the menu button for ALL users.\n"
        "This may take a few seconds.\n\n"
        "Are you sure?",
        reply_markup=reply_markup
    )

async def reset_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reset menu confirmation"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    if not is_admin(user.id):
        await query.edit_message_text("❌ Not authorized.")
        return
    
    if query.data == "reset_menu_cancel":
        await query.edit_message_text("❌ Cancelled.")
        return
    
    if query.data == "reset_menu_confirm":
        await query.edit_message_text("🔄 Resetting menu for all users... This may take a moment.")
        
        try:
            session = db.get_session()
            all_users = session.query(User).all()
            session.close()
            
            count = 0
            failed = 0
            
            for user_obj in all_users:
                try:
                    await context.bot.set_chat_menu_button(
                        chat_id=user_obj.telegram_id,
                        menu_button={"type": "default"}
                    )
                    count += 1
                    await asyncio.sleep(0.1)
                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to reset menu for {user_obj.telegram_id}: {e}")
            
            await query.edit_message_text(
                f"✅ Menu button reset for {count} users.\n"
                f"❌ Failed: {failed}"
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")

# ============================================
# ADMIN COMMANDS
# ============================================

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    pending_w = db.get_pending_withdrawals()

    if not pending_w:
        await update.message.reply_text(
            "📋 No pending withdrawals." + get_community_footer(),
            parse_mode='Markdown'
        )
        return

    text = "📋 PENDING WITHDRAWALS\n\n"
    for w in pending_w:
        user_obj = db.get_user_by_id(w.user_id)
        username = user_obj.username if user_obj else "Unknown"
        text += f"ID: {w.id}\n"
        text += f"👤 User: @{username}\n"
        text += f"💰 Amount: ${w.amount:.2f} USDT\n"
        text += f"🔒 Fee (5%): ${w.fee:.2f} USDT\n"
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
            "📋 Incorrect Usage\n\n"
            "Please use: /complete_payout <withdrawal_id> <tx_hash>\n\n"
            "Example: /complete_payout 123 0xdef456...\n\n"
            "This command completes a pending withdrawal.\n"
            "The withdrawal_id is the number from /pending."
            + get_community_footer()
        )
        return

    try:
        withdrawal_id = int(context.args[0])
        tx_hash = context.args[1]
    except ValueError:
        await update.message.reply_text("❌ Invalid withdrawal ID.")
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
            f"🔒 Fee Collected: ${withdrawal.fee:.2f} USDT\n"
            f"🔗 TX: {tx_hash}\n"
            f"⛓️ Network: Polygon"
            + get_community_footer(),
            parse_mode='Markdown'
        )

        try:
            channel_message = (
                f"📤 **Withdrawal Completed!**\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💵 Amount: **${withdrawal.net_amount:.2f} USDT**\n"
                f"⛓️ Network: Polygon\n"
                f"🔗 TX: [View on Polygonscan](https://polygonscan.com/tx/{tx_hash})\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🏦 Project Wallet: `{PROJECT_WALLET}`"
            )
            await send_to_channel(context.bot, channel_message)
        except Exception as e:
            logger.error(f"Error sending to channel: {e}")

        user_obj = db.get_user_by_id(withdrawal.user_id)
        if user_obj:
            try:
                await context.bot.send_message(
                    chat_id=user_obj.telegram_id,
                    text=f"✅ Your withdrawal request has been processed!\n\n"
                         f"💰 Amount: ${withdrawal.amount:.2f} USDT\n"
                         f"💵 Net: ${withdrawal.net_amount:.2f} USDT\n"
                         f"🔗 TX: [View on Polygonscan](https://polygonscan.com/tx/{tx_hash})\n"
                         f"⛓️ Network: Polygon\n\n"
                         f"Check your wallet!"
                         + get_community_footer(),
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error notifying user: {e}")
    else:
        await update.message.reply_text(f"❌ Failed to update withdrawal {withdrawal_id}.")

async def pending_fees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("pending_fees command received!")
    user = update.effective_user
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    total_fees = db.get_uncollected_fees_total()
    fees = db.get_uncollected_fees()

    if total_fees == 0:
        await update.message.reply_text("📋 No uncollected fees.\n\nAll withdrawal fees have been collected! ✅" + get_community_footer())
        return

    text = "💰 Uncollected Withdrawal Fees\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 Total: ${total_fees:.2f} USDT\n"
    text += f"📋 Number of fees: {len(fees)}\n\n"
    
    if len(fees) > 0:
        text += "📝 Recent fees:\n"
        for fee in fees[:5]:
            user_obj = db.get_user_by_id(fee.user_id)
            username = user_obj.username if user_obj else "Unknown"
            text += f"  - ${fee.amount:.2f} from @{username}\n"
        if len(fees) > 5:
            text += f"  ... and {len(fees) - 5} more\n"
    
    text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    text += f"To collect all fees:\n"
    text += f"/collect_fees TX_HASH\n\n"
    text += f"⚠️ This will mark ALL uncollected fees as collected."
    
    await update.message.reply_text(text + get_community_footer())

async def collect_fees(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("collect_fees command received!")
    user = update.effective_user
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ Usage: /collect_fees <tx_hash>\n\n"
            "Example: /collect_fees 0xabc123..."
            + get_community_footer()
        )
        return

    tx_hash = context.args[0]
    
    total_fees = db.get_uncollected_fees_total()
    if total_fees == 0:
        await update.message.reply_text("📋 No uncollected fees to collect." + get_community_footer())
        return

    count = db.mark_fees_collected(tx_hash)
    
    await update.message.reply_text(
        f"✅ Fees Collected!\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Total collected: ${total_fees:.2f} USDT\n"
        f"📋 Number of fees: {count}\n"
        f"🔗 TX: {tx_hash}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"All fees have been marked as collected."
        + get_community_footer()
    )

async def test_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("❌ Not authorized.")
        return
    
    await update.message.reply_text("📤 Sending test message to channel...")
    
    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text="✅ PlantUSDT bot is connected to the transaction channel!",
            parse_mode='Markdown'
        )
        await update.message.reply_text("✅ Message sent to channel successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending to channel: {e}")

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    help_text = """ADMIN COMMANDS

/pending - View all pending withdrawals
/complete_payout <id> <tx_hash> - Mark a payout as completed
/pending_fees - View total uncollected withdrawal fees
/collect_fees <tx_hash> - Collect ALL uncollected fees
/test_channel - Test channel connection
/reset_referral <user_id> - Reset a user's referral status
/reset_menu_all - Reset the four-square menu button for ALL users

TASK MANAGEMENT:
/add_task <title> | <description> | <reward> - Create a new task
/list_tasks - List all active tasks
/delete_task <task_id> - Delete a task
/complete_task <user_id> <task_id> - Mark task as completed for a user

Example:
/pending
/complete_payout 1 0xabc123...
/pending_fees
/collect_fees 0xdef456...
/test_channel
/reset_referral 123456789
/reset_menu_all

/add_task Watch 3 Ads | Watch 3 rewarded ads | 0.10
/list_tasks
/delete_task 1
/complete_task 123456789 1

Transactions are on Polygon (MATIC) network using USDT on Polygon

Fee Collection System:
- Fees are automatically tracked when withdrawals are completed
- Use /pending_fees to see how much is uncollected
- Use /collect_fees TX_HASH to mark all fees as collected
- Send the total fees to your personal wallet in one transaction"""

    await update.message.reply_text(help_text + get_community_footer())

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
            + get_community_footer()
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
            + get_community_footer()
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

# ============================================
# ADMIN TASK COMMANDS
# ============================================

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to add a new task"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "❌ Usage: /add_task <title> | <description> | <reward>\n\n"
            "Example: /add_task Watch 3 Ads | Watch 3 rewarded ads | 0.10\n\n"
            "Note: Use | as separator between title, description, and reward."
            + get_community_footer(),
            parse_mode='Markdown'
        )
        return

    try:
        full_text = ' '.join(args)
        parts = full_text.split('|')
        
        if len(parts) != 3:
            await update.message.reply_text(
                "❌ Invalid format. Use: /add_task <title> | <description> | <reward>"
                + get_community_footer(),
                parse_mode='Markdown'
            )
            return

        title = parts[0].strip()
        description = parts[1].strip()
        reward = float(parts[2].strip())

        if reward <= 0:
            await update.message.reply_text("❌ Reward must be greater than 0.")
            return

        session = db.get_session()
        success, result = create_task(title, description, reward, user.id, session)
        session.close()

        if success:
            await update.message.reply_text(
                f"✅ Task created successfully!\n\n"
                f"📌 Title: {title}\n"
                f"📝 Description: {description}\n"
                f"💰 Reward: ${reward:.2f} USDT\n"
                f"🆔 Task ID: {result.id}\n\n"
                f"Users can see this task in the Mini App!"
                + get_community_footer(),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ Failed to create task: {result}")
            
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid reward amount. Please enter a valid number."
            + get_community_footer(),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error adding task: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to list all tasks"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    session = db.get_session()
    tasks = get_all_tasks(session)
    session.close()

    if not tasks:
        await update.message.reply_text(
            "📋 No active tasks found."
            + get_community_footer(),
            parse_mode='Markdown'
        )
        return

    text = "📋 **Active Tasks**\n\n"
    for task in tasks:
        text += f"🆔 ID: `{task.id}`\n"
        text += f"📌 Title: {task.title}\n"
        text += f"📝 Description: {task.description}\n"
        text += f"💰 Reward: ${task.reward:.2f} USDT\n"
        text += f"📅 Created: {task.created_at.strftime('%Y-%m-%d %H:%M')}\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n"

    await update.message.reply_text(
        text + get_community_footer(),
        parse_mode='Markdown'
    )

async def delete_task_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to delete a task"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 1:
        await update.message.reply_text(
            "❌ Usage: /delete_task <task_id>\n\n"
            "Example: /delete_task 1"
            + get_community_footer(),
            parse_mode='Markdown'
        )
        return

    try:
        task_id = int(context.args[0])
        session = db.get_session()
        success, msg = delete_task(task_id, session)
        session.close()

        if success:
            await update.message.reply_text(
                f"✅ Task #{task_id} deleted successfully!"
                + get_community_footer(),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ {msg}"
                + get_community_footer(),
                parse_mode='Markdown'
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid task ID. Please enter a valid number."
            + get_community_footer(),
            parse_mode='Markdown'
        )

async def complete_task_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to mark a task as completed for a user"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Usage: /complete_task <user_id> <task_id>\n\n"
            "Example: /complete_task 123456789 1"
            + get_community_footer(),
            parse_mode='Markdown'
        )
        return

    try:
        target_user_id = int(context.args[0])
        task_id = int(context.args[1])

        session = db.get_session()
        success, msg = complete_task(target_user_id, task_id, session)
        session.close()

        if success:
            await update.message.reply_text(
                f"✅ Task #{task_id} completed for user {target_user_id}!"
                + get_community_footer(),
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ {msg}"
                + get_community_footer(),
                parse_mode='Markdown'
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid IDs. Please enter valid numbers."
            + get_community_footer(),
            parse_mode='Markdown'
        )

# ============================================
# REFERRAL SYSTEM COMMANDS
# ============================================

async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"📊 upgrade command received from user {user.id}")
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    # Update user info
    db.update_user_info(user.id, user.username, user.first_name)
    
    args = context.args
    if len(args) < 1:
        tier_list = "\n".join([f"{info['emoji']} {tier.title()}: {info['bonus_percent']}% (${info['price']:.2f})" for tier, info in REFERRAL_TIERS.items() if tier != "free"])
        await update.message.reply_text(
            f"📊 **Upgrade Your Referral Tier**\n\n"
            f"Permanently increase your referral bonus!\n\n"
            f"Available tiers:\n{tier_list}\n\n"
            f"💡 Example: Friend deposits $100 → you earn 5% at Diamond tier\n\n"
            f"Usage: `/upgrade [tier]`\n"
            f"Example: `/upgrade diamond`"
            + get_community_footer(),
            parse_mode='Markdown'
        )
        return
    
    tier = args[0].lower()
    if tier not in REFERRAL_TIERS:
        await update.message.reply_text(
            f"❌ Invalid tier. Available: {', '.join([t for t in REFERRAL_TIERS.keys() if t != 'free'])}"
            + get_community_footer(),
            parse_mode='Markdown'
        )
        return
    
    if tier == "free":
        await update.message.reply_text(
            "🌱 You're already on the Free tier (1%).\n\n"
            "Upgrade to earn more from your referrals!\n"
            "Use `/upgrade` to see available tiers."
            + get_community_footer(),
            parse_mode='Markdown'
        )
        return
    
    session = db.get_session()
    try:
        user_obj = session.query(User).filter_by(telegram_id=user.id).first()
        if not user_obj:
            await update.message.reply_text("❌ User not found.")
            session.close()
            return
        
        current_tier = user_obj.referral_tier or "free"
        
        if current_tier == tier:
            await update.message.reply_text(
                f"✅ You're already on the {REFERRAL_TIERS[tier]['emoji']} {tier.title()} tier!\n"
                f"Bonus: {REFERRAL_TIERS[tier]['bonus_percent']}%"
                + get_community_footer(),
                parse_mode='Markdown'
            )
            session.close()
            return
        
        current_price = REFERRAL_TIERS[current_tier]["price"]
        new_price = REFERRAL_TIERS[tier]["price"]
        cost = new_price - current_price
        
        if cost <= 0:
            await update.message.reply_text("❌ Invalid upgrade path.")
            session.close()
            return
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm Upgrade", callback_data=f"upgrade_confirm_{tier}"),
                InlineKeyboardButton("❌ Cancel", callback_data="upgrade_cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📊 **Upgrade to {REFERRAL_TIERS[tier]['emoji']} {tier.title()} Tier**\n\n"
            f"Current tier: {REFERRAL_TIERS[current_tier]['emoji']} {current_tier.title()} ({REFERRAL_TIERS[current_tier]['bonus_percent']}%)\n"
            f"New tier: {REFERRAL_TIERS[tier]['emoji']} {tier.title()} ({REFERRAL_TIERS[tier]['bonus_percent']}%)\n\n"
            f"💰 Cost: **${cost:.2f}** USDT\n"
            f"💵 Your balance: **${user_obj.balance:.2f}**\n\n"
            f"⚠️ This is a PERMANENT upgrade. No refunds.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        session.close()
        
    except Exception as e:
        logger.error(f"Upgrade error: {e}")
        await update.message.reply_text("❌ Error processing upgrade. Please try again.")
        session.close()

async def upgrade_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    if data == "upgrade_cancel":
        await query.edit_message_text("❌ Upgrade cancelled.", parse_mode='Markdown')
        return
    
    if data.startswith("upgrade_confirm_"):
        tier = data.replace("upgrade_confirm_", "")
        
        session = db.get_session()
        try:
            user_obj = session.query(User).filter_by(telegram_id=user.id).first()
            if not user_obj:
                await query.edit_message_text("❌ User not found.")
                session.close()
                return
            
            success, msg = upgrade_referral_tier(user_obj.id, tier, session)
            
            if success:
                await query.edit_message_text(
                    f"{msg}\n\n"
                    f"💰 New balance: **${user_obj.balance:.2f}**\n"
                    f"📊 New bonus: **{REFERRAL_TIERS[tier]['bonus_percent']}%**\n\n"
                    f"💡 Your referrals will now earn you more!\n"
                    f"Share your referral link to start earning."
                    + get_community_footer(),
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(f"❌ {msg}" + get_community_footer(), parse_mode='Markdown')
            session.close()
            
        except Exception as e:
            logger.error(f"Upgrade callback error: {e}")
            await query.edit_message_text("❌ Error processing upgrade. Please try again.")
            session.close()

async def referral_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"📊 referral_stats command received from user {user.id}")
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    # Update user info
    db.update_user_info(user.id, user.username, user.first_name)
    
    session = db.get_session()
    try:
        user_obj = session.query(User).filter_by(telegram_id=user.id).first()
        if not user_obj:
            await update.message.reply_text("❌ User not found.")
            session.close()
            return
        
        stats = get_referral_stats(user_obj.id, session)
        logger.info(f"📊 Stats retrieved: {stats}")
        
        if not stats:
            await update.message.reply_text("❌ Error loading stats.")
            session.close()
            return
        
        response = f"📊 **Your Referral Stats**\n\n"
        response += f"{stats['tier_emoji']} **Tier:** {stats['current_tier'].title()}\n"
        response += f"📈 **Bonus:** {stats['tier_bonus']}%\n"
        response += f"━━━━━━━━━━━━━━━━━━━━\n"
        response += f"👥 **Total Referrals:** {stats['total_referred']}\n"
        response += f"✅ **Active Referrals:** {stats['active_referrals']}\n"
        response += f"⏳ **Pending Active:** {stats['pending_active']}\n"
        response += f"💰 **Active Bonus Earned:** ${stats['active_bonus_earned']:.3f}\n"
        response += f"💎 **Spent on Upgrades:** ${stats['upgrade_spent']:.2f}\n\n"
        
        if stats['next_tier']:
            response += f"⬆️ **Next Tier:** {REFERRAL_TIERS[stats['next_tier']]['emoji']} {stats['next_tier'].title()}\n"
            response += f"📈 **Next Bonus:** {stats['next_tier_bonus']}%\n"
            response += f"💰 **Upgrade Cost:** ${stats['next_tier_price']:.2f}\n\n"
            response += f"Upgrade with: `/upgrade {stats['next_tier']}`"
        else:
            response += f"🏆 **You're at the highest tier!**\n"
            response += f"💎 Maximum bonus: {stats['tier_bonus']}%\n\n"
            response += f"Share your referral link to earn more!"
        
        response += get_community_footer()
        
        await update.message.reply_text(response, parse_mode='Markdown')
        logger.info(f"✅ referral_stats response sent to user {user.id}")
        
    except Exception as e:
        logger.error(f"Referral stats error: {e}")
        await update.message.reply_text(f"❌ Error fetching stats: {str(e)}")
    finally:
        session.close()

# ============================================
# MANUAL BALANCE UPDATE WITH AUDIT LOG
# ============================================

async def manual_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to manually update a user's balance with audit logging"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ Usage: /manual_balance <user_id> <amount> <description>\n\n"
            "Example: /manual_balance 123456789 0.50 'Bonus for testing'\n\n"
            "Use negative amount to deduct: /manual_balance 123456789 -0.50 'Fee adjustment'"
            + get_community_footer(),
            parse_mode='Markdown'
        )
        return

    try:
        target_user_id = int(context.args[0])
        amount = Decimal(str(context.args[1]))
        description = ' '.join(context.args[2:])
        
        session = db.get_session()
        target_user = session.query(User).filter_by(telegram_id=target_user_id).first()
        
        if not target_user:
            await update.message.reply_text(f"❌ User {target_user_id} not found.")
            session.close()
            return
        
        old_balance = Decimal(target_user.balance or 0)
        new_balance = old_balance + amount
        
        target_user.balance = new_balance
        target_user.total_earnings_all_time = (target_user.total_earnings_all_time or Decimal('0')) + amount
        
        # Log to audit log
        audit = AuditLog(
            user_id=target_user.id,
            action='manual_update',
            field_changed='balance',
            old_value=float(old_balance),
            new_value=float(new_balance),
            amount=float(amount),
            description=description,
            source='admin',
            created_by=user.id,
            created_at=datetime.utcnow()
        )
        session.add(audit)
        session.commit()
        
        await update.message.reply_text(
            f"✅ Balance updated for @{target_user.username or 'User'}!\n\n"
            f"📊 Old balance: ${old_balance:.2f}\n"
            f"📊 New balance: ${new_balance:.2f}\n"
            f"💰 Amount: ${amount:.2f}\n"
            f"📝 Description: {description}\n"
            f"🆔 User ID: {target_user_id}"
            + get_community_footer(),
            parse_mode='Markdown'
        )
        session.close()
        
    except ValueError as e:
        await update.message.reply_text(f"❌ Invalid input: {e}")
    except Exception as e:
        session.rollback()
        logger.error(f"Error in manual_balance: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
        session.close()

# ============================================
# POST_INIT — Sets the commands and starts the deposit scanner
# ============================================

async def post_init(application: Application):
    """Configure the Telegram menu and start the deposit scanner."""
    try:
        # Set the commands that will appear in the four-square menu
        await application.bot.set_my_commands([
            ("balance", "👛 Check your balance"),
            ("referrals", "👥 View your referrals"),
            ("withdraw", "🏦 Withdraw your USDT"),
            ("app", "🌱 Open Mini App")
        ])
        logger.info("✅ Bot commands configured for menu")
    except Exception as e:
        logger.warning(f"⚠️ Could not configure commands: {e}")

    async def start_deposit_scanner():
        while True:
            try:
                await deposit_scanner.scan_for_deposits(application.bot)
            except Exception as e:
                logger.error(f"Error in deposit scanner loop: {e}")
            await asyncio.sleep(300)

    application.create_task(start_deposit_scanner())
    logger.info("🔍 Deposit scanner task started")


# ============================================
# MAIN FUNCTION
# ============================================

def main():
    global application
    try:
        scheduler.start()

        application = Application.builder().token(Config.BOT_TOKEN).post_init(post_init).build()

        # User commands
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("app", app_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("referrals", referrals_command))
        application.add_handler(CommandHandler("withdraw", withdraw_command))
        application.add_handler(CommandHandler("reset_menu_all", reset_menu_all))

        # Web App Data handler
        application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_web_app_data))

        # Share referral callback
        application.add_handler(CallbackQueryHandler(share_referral_callback, pattern="^share_referral_"))

        # Reset menu callback
        application.add_handler(CallbackQueryHandler(reset_menu_callback, pattern="^reset_menu_"))

        # Admin commands
        application.add_handler(CommandHandler("pending", pending))
        application.add_handler(CommandHandler("complete_payout", complete_payout))
        application.add_handler(CommandHandler("pending_fees", pending_fees))
        application.add_handler(CommandHandler("collect_fees", collect_fees))
        application.add_handler(CommandHandler("test_channel", test_channel))
        application.add_handler(CommandHandler("admin_help", admin_help))
        application.add_handler(CommandHandler("reset_referral", reset_referral))
        application.add_handler(CommandHandler("manual_balance", manual_balance))

        # Admin task commands
        application.add_handler(CommandHandler("add_task", add_task))
        application.add_handler(CommandHandler("list_tasks", list_tasks))
        application.add_handler(CommandHandler("delete_task", delete_task_cmd))
        application.add_handler(CommandHandler("complete_task", complete_task_cmd))

        # Referral system commands
        application.add_handler(CommandHandler("upgrade", upgrade))
        application.add_handler(CommandHandler("referral_stats", referral_stats))
        application.add_handler(CallbackQueryHandler(upgrade_callback, pattern="^upgrade_"))

        logger.info("🌱 PlantUSDT Bot started! Press Ctrl+C to stop.")
        logger.info(f"📱 Mini App URL: {VERCEL_URL}")
        logger.info("🔍 Deposit scanner running on Polygon (checks every 5 minutes)")
        logger.info("📌 Bot commands configured for four-square menu")
        logger.info("📢 Community footer added to all messages")
        logger.info("📊 Transaction channel: @PlantUSDTtransactions")
        logger.info("💰 Fee collection system active")
        logger.info("📈 Referral system with tier upgrades active")
        logger.info("📋 Task management system active")
        logger.info("📩 Web App Data handler active for referral sharing")
        logger.info("🔄 User info (name/username) auto-updates on each interaction")
        logger.info("📝 Audit log table active for all balance changes")
        logger.info("⚙️ Manual balance command available: /manual_balance")
        logger.info("✅ Active referral bonus system fully fixed")
        logger.info("✅ Active referrals now require investment (30+ ads removed)")
        logger.info("💰 Referral tier prices updated: Bronze $42, Silver $80, Gold $120, Diamond $160")
        logger.info("📊 Daily ad limit increased to 100")
        logger.info("📱 Commands: /balance, /referrals, /withdraw, /app, /reset_menu_all")

        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        raise

if __name__ == "__main__":
    main()

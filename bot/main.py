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
VERCEL_URL = "https://plant-usdt.vercel.app?v=6"

# Project wallet - blocked from user use
PROJECT_WALLET = '0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76'

# Admin check function
def is_admin(user_id: int) -> bool:
    user = db.get_user(user_id)
    return user and user.is_admin

# ============================================
# START COMMAND - WITH REFERRAL HANDLING
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
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
/invest <amount> <days> - Invest directly
/withdraw <amount> - Request withdrawal
/deposit - Get deposit address
/history - Recent transactions

Use /app to open the Mini App!"""

        keyboard = [
            [InlineKeyboardButton("🌱 Open PlantUSDT", web_app=WebAppInfo(url=VERCEL_URL))]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        return

    # ============================================
    # REFERRAL HANDLING - ONLY FOR NEW USERS
    # SILENTLY IGNORE FOR EXISTING USERS
    # ============================================
    if context.args and len(context.args) > 0:
        referral_code = context.args[0]
        
        # Only process if user can still be referred
        if existing_user.can_be_referred and existing_user.referred_by is None:
            seconds_since_creation = (now - existing_user.created_at).total_seconds()
            
            if seconds_since_creation <= 180:  # 3 minutes
                referrer = db.get_user_by_referral_code(referral_code)
                if referrer and referrer.id != existing_user.id:
                    # Apply referral
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
                            f"💡 Your referrer will earn 5% from your future deposits!"
                        )
                        
                        try:
                            await context.bot.send_message(
                                chat_id=referrer.telegram_id,
                                text=f"🎉 **New Referral!**\n\n"
                                     f"@{existing_user.username or 'User'} accepted your referral!\n"
                                     f"💡 You will earn 5% from their future deposits!"
                            )
                        except Exception as e:
                            logger.error(f"Error notifying referrer: {e}")
                        
                        session.close()
                        return
                    session.close()
            # If referral window expired, silently ignore (no error message)
        # If user already has a referrer, silently ignore

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
# APP COMMAND
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
# INTERACTIVE COMMANDS
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
/invest <amount> <days> - Invest directly from chat
/withdraw <amount> - Request withdrawal
/deposit - Get deposit address
/history - Recent transactions

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
        lock_days = inv.lock_period
        unlock_date = inv.unlock_date.strftime('%Y-%m-%d %H:%M') if inv.unlock_date else "N/A"
        text += f"🌾 Field #{inv.field_number}: **${inv.amount:.2f}** USDT\n"
        text += f"   🔒 Locked for {lock_days} days\n"
        text += f"   📅 Unlocks: {unlock_date} UTC\n\n"
    
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
        "💡 If you have issues with deposits, please include your transaction hash and user ID."
    )

# ============================================
# INVEST COMMAND - Direct from Bot
# ============================================

async def invest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Invest directly from bot: /invest 10 7 (amount days)"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Usage: /invest <amount> <days>\n\n"
            "Example: /invest 10 7 (invest $10 for 7 days)\n"
            "Days: 1, 7, or 30\n"
            "Amount: $5 - $100"
        )
        return
    
    try:
        amount = float(args[0])
        days = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount or days. Please use numbers.")
        return
    
    if days not in [1, 7, 30]:
        await update.message.reply_text("❌ Days must be 1, 7, or 30")
        return
    
    if amount < 5 or amount > 100:
        await update.message.reply_text("❌ Amount must be between $5 and $100")
        return
    
    user_data = db.get_user(user.id)
    if not user_data:
        await update.message.reply_text("❌ Please /start first")
        return
    
    if user_data.balance < amount:
        await update.message.reply_text(f"❌ Insufficient balance. Your balance is ${user_data.balance:.2f}")
        return
    
    session = db.get_session()
    
    # Find available field
    existing = session.query(Investment).filter_by(
        user_id=user_data.id,
        is_active=True
    ).all()
    
    used_fields = [inv.field_number for inv in existing]
    available_fields = [1, 2, 3]
    field_number = None
    for f in available_fields:
        if f not in used_fields:
            field_number = f
            break
    
    if not field_number:
        await update.message.reply_text("❌ All fields are occupied. Wait for one to unlock.")
        session.close()
        return
    
    expected_return = investment_service.calculate_return(amount, days)
    unlock_date = datetime.utcnow() + timedelta(days=days)
    
    investment = Investment(
        user_id=user_data.id,
        field_number=field_number,
        amount=amount,
        lock_period=days,
        unlock_date=unlock_date,
        expected_return=expected_return,
        start_date=datetime.utcnow(),
        end_date=unlock_date,
        is_active=True,
        is_locked=True
    )
    session.add(investment)
    
    user_data.balance -= amount
    user_data.total_invested += amount
    
    session.commit()
    session.close()
    
    await update.message.reply_text(
        f"✅ **Investment Successful!**\n\n"
        f"🌱 Field #{field_number}\n"
        f"💰 Amount: **${amount:.2f}**\n"
        f"📅 Lock Period: **{days} days**\n"
        f"📈 Expected Return: **${expected_return:.2f}**\n"
        f"🔓 Unlock Date: {unlock_date.strftime('%Y-%m-%d %H:%M')} UTC\n"
        f"⛓️ Network: Polygon\n\n"
        f"💵 Your balance: **${user_data.balance:.2f}**"
    )

# ============================================
# WITHDRAW COMMAND - Direct from Bot
# ============================================

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request withdrawal: /withdraw 5"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "❌ Usage: /withdraw <amount>\n\n"
            "Example: /withdraw 5 (withdraw $5 USDT)\n"
            "Minimum: $2"
        )
        return
    
    try:
        amount = float(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please use a number.")
        return
    
    user_data = db.get_user(user.id)
    if not user_data:
        await update.message.reply_text("❌ Please /start first")
        return
    
    if amount < 2:
        await update.message.reply_text("❌ Minimum withdrawal is $2")
        return
    
    if not user_data.wallet_address:
        await update.message.reply_text("❌ You need to connect a wallet first in the Mini App.\n\nUse /app to open the Mini App.")
        return
    
    if user_data.balance < amount:
        await update.message.reply_text(f"❌ Insufficient balance. Your balance is ${user_data.balance:.2f}")
        return
    
    # Create withdrawal
    fee = amount * 0.10
    net = amount - fee
    
    withdrawal = Withdrawal(
        user_id=user_data.id,
        amount=amount,
        fee=fee,
        net_amount=net,
        wallet_address=user_data.wallet_address,
        status='pending'
    )
    
    session = db.get_session()
    session.add(withdrawal)
    user_data.balance -= amount
    session.commit()
    session.close()
    
    await update.message.reply_text(
        f"✅ **Withdrawal Request Submitted!**\n\n"
        f"💰 Amount: **${amount:.2f}**\n"
        f"🔒 Fee (10%): **${fee:.2f}**\n"
        f"💵 Net: **${net:.2f}**\n"
        f"📤 Wallet: {user_data.wallet_address[:10]}...{user_data.wallet_address[-8:]}\n"
        f"⏳ Status: **Pending** (admin review)\n"
        f"⛓️ Network: Polygon\n\n"
        f"💵 Your new balance: **${user_data.balance:.2f}**"
    )

# ============================================
# DEPOSIT COMMAND - Show Address
# ============================================

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show deposit address"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    await update.message.reply_text(
        f"💰 **Deposit USDT on Polygon**\n\n"
        f"📌 Deposit Address:\n`{PROJECT_WALLET}`\n\n"
        f"⛓️ Network: **Polygon (MATIC)**\n"
        f"💵 Token: **USDT**\n"
        f"🔢 Decimals: **6**\n"
        f"💸 Min Deposit: **$5 USDT**\n\n"
        f"⚠️ Send USDT **FROM YOUR CONNECTED WALLET** only!\n"
        f"Sending from a different wallet or network = **PERMANENT LOSS**.\n\n"
        f"🔍 Deposits are detected automatically every 5 minutes.\n"
        f"❓ Need help? Contact @Alex_PlantUSDT"
    )

# ============================================
# HISTORY COMMAND - Recent Transactions
# ============================================

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent transactions"""
    user = update.effective_user
    
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ Too many requests. Please wait.")
        return
    
    user_data = db.get_user(user.id)
    if not user_data:
        await update.message.reply_text("❌ Please /start first")
        return
    
    session = db.get_session()
    
    deposits = session.query(Deposit).filter_by(user_id=user_data.id).order_by(Deposit.id.desc()).limit(3).all()
    withdrawals = session.query(Withdrawal).filter_by(user_id=user_data.id).order_by(Withdrawal.id.desc()).limit(3).all()
    
    session.close()
    
    text = "📜 **Recent Transactions**\n\n"
    
    if deposits:
        text += "💰 **Deposits:**\n"
        for d in deposits[:3]:
            text += f"  +${d.amount:.2f} ({d.confirmed_at.strftime('%m/%d %H:%M')})\n"
    
    if withdrawals:
        text += "\n📤 **Withdrawals:**\n"
        for w in withdrawals[:3]:
            status_emoji = "✅" if w.status == "completed" else "⏳"
            text += f"  {status_emoji} ${w.amount:.2f} ({w.status})\n"
    
    if not deposits and not withdrawals:
        text += "No transactions yet.\n"
    
    ad_earnings = user_data.total_ad_earnings or 0
    if ad_earnings > 0:
        text += f"\n📺 **Ad Earnings:** +${ad_earnings:.3f}\n"
    
    text += f"\n💰 Balance: **${user_data.balance:.2f}**"
    text += f"\n\n📊 Full history: Use /app and go to Transaction History"
    
    await update.message.reply_text(text)

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
        scheduler.start()

        application = Application.builder().token(Config.BOT_TOKEN).build()

        # User commands
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("app", app_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("support", support_command))
        application.add_handler(CommandHandler("invest", invest_command))
        application.add_handler(CommandHandler("withdraw", withdraw_command))
        application.add_handler(CommandHandler("deposit", deposit_command))
        application.add_handler(CommandHandler("history", history_command))

        # Admin commands
        application.add_handler(CommandHandler("pending", pending_withdrawals))
        application.add_handler(CommandHandler("complete_payout", complete_payout))
        application.add_handler(CommandHandler("adminhelp", admin_help))
        application.add_handler(CommandHandler("reset_referral", reset_referral))

        async def start_deposit_scanner():
            while True:
                try:
                    await deposit_scanner.scan_for_deposits(application.bot)
                except Exception as e:
                    logger.error(f"Error in deposit scanner loop: {e}")
                await asyncio.sleep(300)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(start_deposit_scanner())

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
        logger.info("🤖 Interactive commands: /invest, /withdraw, /deposit, /history")

        application.run_polling(allowed_updates=Update.ALL_TYPES)

    except Exception as e:
        logger.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    main()

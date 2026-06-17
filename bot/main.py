from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config.settings import Config
from database.db_manager import DatabaseManager
from services.investment import InvestmentService
from services.wallet import WalletService
from services.deposit_scanner import DepositScanner
import logging
import asyncio
from datetime import datetime

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Initialize services
db = DatabaseManager()
investment_service = InvestmentService()
wallet_service = WalletService()
deposit_scanner = DepositScanner()

# Create tables
db.create_tables()

# Vercel URL for Mini App
VERCEL_URL = "https://plant-usdt.vercel.app"  # Change this to your actual Vercel URL

# Start command
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

👥 REFERRAL BONUS:
Share your referral link and earn 5% from your friends' deposits!

Use /invest to get started!
Use /dashboard to check your stats!
Use /app to open the Mini App!"""
        
        # WebApp button
        keyboard = [
            [InlineKeyboardButton("🌱 Open PlantUSDT App", web_app=WebAppInfo(url=VERCEL_URL))],
            [InlineKeyboardButton("💰 Invest", callback_data="invest_amount")],
            [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    else:
        # WebApp button for existing users
        keyboard = [
            [InlineKeyboardButton("🌱 Open PlantUSDT App", web_app=WebAppInfo(url=VERCEL_URL))],
            [InlineKeyboardButton("💰 Invest", callback_data="invest_amount")],
            [InlineKeyboardButton("📊 Dashboard", callback_data="dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Welcome back, {user.first_name}! 🌱\n\n"
            f"Open the PlantUSDT App below:",
            reply_markup=reply_markup
        )

# App command - opens Mini App
async def app_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("🌱 Open PlantUSDT App", web_app=WebAppInfo(url=VERCEL_URL))
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🌱 Open the PlantUSDT Mini App:",
        reply_markup=reply_markup
    )

# Invest command
async def invest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = db.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("Please use /start first to register!")
        return
    
    keyboard = [
        [InlineKeyboardButton("💰 Invest USDT", callback_data="invest_amount")],
        [InlineKeyboardButton("📊 My Investments", callback_data="my_investments")],
        [InlineKeyboardButton("🏦 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("💳 Set Wallet", callback_data="set_wallet")],
        [InlineKeyboardButton("🌱 Open App", web_app=WebAppInfo(url=VERCEL_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"💰 Investment Menu\n\n"
        f"• 2% daily return\n"
        f"• 30 days investment period\n"
        f"• Minimum: ${Config.MIN_INVESTMENT} USDT\n"
        f"• Your Balance: ${db_user.balance:.2f} USDT\n\n"
        f"Select an option:",
        reply_markup=reply_markup
    )

# Dashboard command
async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = db.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("Please use /start first to register!")
        return
    
    investments = db.get_user_investments(db_user.id)
    active_investments = [inv for inv in investments if inv.is_active]
    completed_investments = [inv for inv in investments if inv.is_completed]
    
    # Calculate today's earnings
    today_earnings = 0
    for inv in active_investments:
        today_earnings += inv.amount * 0.02
    
    dashboard_text = f"""📊 YOUR DASHBOARD

👤 User: @{user.username or 'No username'}
📅 Member since: {db_user.created_at.strftime('%d/%m/%Y')}

💰 BALANCE: ${db_user.balance:.2f} USDT
📈 TOTAL INVESTED: ${db_user.total_invested:.2f} USDT
💵 TOTAL EARNED: ${db_user.total_earned:.2f} USDT
💳 TOTAL DEPOSITED: ${db_user.total_deposited:.2f} USDT

💼 ACTIVE INVESTMENTS: {len(active_investments)}
✅ COMPLETED INVESTMENTS: {len(completed_investments)}

📊 TODAY'S EARNINGS: ${today_earnings:.2f} USDT

Use /invest to grow your USDT!"""
    
    keyboard = [[InlineKeyboardButton("🌱 Open App", web_app=WebAppInfo(url=VERCEL_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(dashboard_text, reply_markup=reply_markup)

# Deposit command
async def deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = db.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("Please use /start first to register!")
        return
    
    deposit_text = f"""💳 DEPOSIT INSTRUCTIONS

1️⃣ Send USDT (BEP-20) to this address:
`{Config.WALLET_ADDRESS}`

2️⃣ Minimum deposit: $5 USDT

3️⃣ Your deposit will be automatically detected within 5-15 minutes

⚠️ IMPORTANT:
• ONLY send USDT on BSC (BEP-20) network
• Make sure the network is BSC (BEP-20), NOT ERC-20

📊 NETWORK DETAILS:
• Network: BSC (BEP-20)
• Contract: {Config.USDT_CONTRACT}
• Decimals: 18

Need help? Contact @{Config.ADMIN_USERNAME}"""
    
    keyboard = [
        [InlineKeyboardButton("✅ I've Sent USDT", callback_data="check_deposit")],
        [InlineKeyboardButton("🌱 Open App", web_app=WebAppInfo(url=VERCEL_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(deposit_text, reply_markup=reply_markup, parse_mode='Markdown')

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""❓ HELP CENTER

📚 QUICK GUIDE:
• /start - Start the bot
• /app - Open Mini App
• /invest - Make an investment
• /dashboard - View your stats
• /deposit - Get deposit address
• /withdraw - Request withdrawal
• /setwallet - Set withdrawal address
• /help - Show this message

💡 TIPS:
• Minimum deposit: $5 USDT
• Daily returns: 2% for 30 days
• Minimum withdrawal: $2 USDT
• 10% fee on withdrawals

🔐 SECURITY:
• Never share your private keys
• Only use official deposit address

📞 SUPPORT:
Need help? Contact: @{Config.ADMIN_USERNAME}

🚀 Start growing your USDT today!"""
    
    keyboard = [[InlineKeyboardButton("🌱 Open App", web_app=WebAppInfo(url=VERCEL_URL))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, reply_markup=reply_markup)

# Set wallet command
async def set_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = db.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("Please use /start first to register!")
        return
    
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "❌ Please provide your BSC wallet address.\n\n"
            "Example: /setwallet 0x123456789...\n\n"
            "You can find your address in your wallet app (SafePal, Trust Wallet, MetaMask, etc.)"
        )
        return
    
    wallet_address = context.args[0]
    
    if not wallet_address.startswith('0x') or len(wallet_address) != 42:
        await update.message.reply_text(
            "❌ Invalid wallet address!\n\n"
            "A BSC wallet address should:\n"
            "• Start with '0x'\n"
            "• Be 42 characters long\n\n"
            "Example: 0x1234567890abcdef1234567890abcdef12345678"
        )
        return
    
    db.update_wallet_address(db_user.id, wallet_address)
    
    await update.message.reply_text(
        f"✅ Wallet address updated successfully!\n\n"
        f"🏦 New address:\n`{wallet_address}`\n\n"
        f"This address will be used for withdrawals.",
        parse_mode='Markdown'
    )

# Callback query handler
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db_user = db.get_user(user.id)
    
    if query.data == "invest_amount":
        await query.edit_message_text(
            "💰 To invest, please send USDT to the deposit address using /deposit\n\n"
            "Once your deposit is confirmed, you can start investing!"
        )
    
    elif query.data == "my_investments":
        investments = db.get_user_investments(db_user.id)
        if not investments:
            await query.edit_message_text("You have no investments yet. Use /deposit to start!")
            return
        
        text = "📊 YOUR INVESTMENTS\n\n"
        for inv in investments:
            status = "🟢 Active" if inv.is_active else "✅ Completed"
            text += f"• ${inv.amount:.2f} USDT - {status}\n"
            text += f"  Paid: ${inv.paid_out:.2f} / ${inv.total_return:.2f}\n\n"
        
        await query.edit_message_text(text)
    
    elif query.data == "withdraw":
        await query.edit_message_text(
            "🏦 WITHDRAWAL\n\n"
            f"💰 Available Balance: ${db_user.balance:.2f} USDT\n"
            f"💵 Minimum Withdrawal: ${Config.MIN_WITHDRAWAL} USDT\n"
            f"🔒 Withdrawal Fee: 10%\n\n"
            "Please use /withdraw command to request a withdrawal."
        )
    
    elif query.data == "set_wallet":
        await query.edit_message_text(
            "💳 SET WITHDRAWAL WALLET\n\n"
            "Please use /setwallet command followed by your BSC wallet address.\n\n"
            "Example: /setwallet 0x123456789..."
        )
    
    elif query.data == "check_deposit":
        await query.edit_message_text(
            "🔍 Checking for deposits...\n\n"
            "Please wait a few moments. Your deposit will be detected automatically.\n"
            "If you just sent USDT, it should appear within 5-15 minutes."
        )
    
    elif query.data == "dashboard":
        # Redirect to dashboard
        await query.edit_message_text("📊 Opening dashboard...")
        # The bot will handle this via the dashboard command

def main():
    """Start the bot"""
    try:
        # Create application
        application = Application.builder().token(Config.BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("app", app_command))
        application.add_handler(CommandHandler("invest", invest))
        application.add_handler(CommandHandler("dashboard", dashboard))
        application.add_handler(CommandHandler("deposit", deposit))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("setwallet", set_wallet))
        application.add_handler(CallbackQueryHandler(callback_handler))
        
        # Start the bot
        logger.info("🌱 PlantUSDT Bot started! Press Ctrl+C to stop.")
        logger.info(f"📱 Mini App URL: {VERCEL_URL}")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    main()
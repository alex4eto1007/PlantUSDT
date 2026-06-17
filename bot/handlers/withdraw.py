from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, ConversationHandler, CallbackQueryHandler
from database.db_manager import DatabaseManager
from config.settings import Config
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
db = DatabaseManager()

# Conversation states
AMOUNT, CONFIRM = range(2)

async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start withdrawal process"""
    user = update.effective_user
    db_user = db.get_user(user.id)
    
    if not db_user:
        await update.message.reply_text("Please use /start first to register!")
        return ConversationHandler.END
    
    if not db_user.wallet_address:
        await update.message.reply_text(
            "❌ You haven't set a withdrawal wallet address!\n\n"
            "Please use /setwallet 0xYourBSCAddress to set your withdrawal address."
        )
        return ConversationHandler.END
    
    if db_user.balance < Config.MIN_WITHDRAWAL:
        await update.message.reply_text(
            f"❌ Insufficient balance!\n\n"
            f"💰 Your balance: ${db_user.balance:.2f} USDT\n"
            f"💵 Minimum withdrawal: ${Config.MIN_WITHDRAWAL} USDT"
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        f"🏦 WITHDRAWAL\n\n"
        f"💰 Available Balance: ${db_user.balance:.2f} USDT\n"
        f"💵 Minimum: ${Config.MIN_WITHDRAWAL} USDT\n"
        f"🔒 Fee: 10%\n\n"
        f"📝 Enter the amount you want to withdraw (USDT):"
    )
    return AMOUNT

async def withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle withdrawal amount input"""
    user = update.effective_user
    db_user = db.get_user(user.id)
    
    try:
        amount = float(update.message.text)
        
        if amount < Config.MIN_WITHDRAWAL:
            await update.message.reply_text(
                f"❌ Minimum withdrawal is ${Config.MIN_WITHDRAWAL} USDT.\n"
                f"Please enter a larger amount."
            )
            return AMOUNT
        
        if amount > db_user.balance:
            await update.message.reply_text(
                f"❌ Insufficient balance!\n"
                f"Your balance: ${db_user.balance:.2f} USDT"
            )
            return AMOUNT
        
        # Calculate fee
        fee = amount * Config.WITHDRAWAL_FEE
        net_amount = amount - fee
        
        context.user_data['withdraw_amount'] = amount
        context.user_data['withdraw_fee'] = fee
        context.user_data['withdraw_net'] = net_amount
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="confirm_withdraw"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_withdraw")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📋 WITHDRAWAL SUMMARY\n\n"
            f"💰 Amount: ${amount:.2f} USDT\n"
            f"🔒 Fee (10%): ${fee:.2f} USDT\n"
            f"💵 Net Amount: ${net_amount:.2f} USDT\n"
            f"🏦 Wallet: {db_user.wallet_address}\n\n"
            f"Please confirm your withdrawal request:",
            reply_markup=reply_markup
        )
        return CONFIRM
        
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return AMOUNT

async def confirm_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and process withdrawal"""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    db_user = db.get_user(user.id)
    
    amount = context.user_data.get('withdraw_amount')
    fee = context.user_data.get('withdraw_fee')
    net_amount = context.user_data.get('withdraw_net')
    
    if not amount:
        await query.edit_message_text("❌ Something went wrong. Please try again.")
        return ConversationHandler.END
    
    # Create withdrawal request
    withdrawal = db.create_withdrawal(
        user_id=db_user.id,
        amount=amount,
        wallet_address=db_user.wallet_address
    )
    
    # Notify admins
    for admin_id in Config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"""🏦 NEW WITHDRAWAL REQUEST!

👤 User: @{user.username or 'No username'} (ID: {user.id})
💰 Amount: ${withdrawal.amount:.2f} USDT
🔒 Fee: ${withdrawal.fee:.2f} USDT (10%)
💵 Net Amount: ${withdrawal.net_amount:.2f} USDT
🏦 Wallet: {withdrawal.wallet_address}
📅 Requested: {withdrawal.created_at.strftime('%d/%m/%Y %H:%M')} UTC

Status: ⏳ Pending

⚠️ Please process this withdrawal manually!"""
            )
        except Exception as e:
            logger.error(f"Error notifying admin {admin_id}: {e}")
    
    await query.edit_message_text(
        f"✅ WITHDRAWAL REQUEST SUBMITTED!\n\n"
        f"💰 Amount: ${amount:.2f} USDT\n"
        f"🔒 Fee: ${fee:.2f} USDT\n"
        f"💵 Net: ${net_amount:.2f} USDT\n"
        f"🏦 To: {db_user.wallet_address[:10]}...{db_user.wallet_address[-8:]}\n"
        f"📅 Requested: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC\n\n"
        f"⏳ Status: Pending (Manual Processing)\n"
        f"📆 Estimated: 12-24 hours\n\n"
        f"You'll be notified when processed."
    )
    
    return ConversationHandler.END

async def cancel_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel withdrawal"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Withdrawal cancelled.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel withdrawal"""
    await update.message.reply_text("❌ Withdrawal cancelled.")
    return ConversationHandler.END

def get_withdraw_conversation():
    """Get the withdrawal conversation handler"""
    return ConversationHandler(
        entry_points=[CommandHandler("withdraw", withdraw_start)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
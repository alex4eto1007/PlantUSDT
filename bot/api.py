import sys
import os
import asyncio
import time
import logging
import random
import string
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Config FIRST
from config.settings import Config

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from database.db_manager import DatabaseManager
from database.models import User, Withdrawal, Investment, Deposit, DailyPayout, PendingDepositCheck
from sqlalchemy import func

app = Flask(__name__)
logger = logging.getLogger(__name__)

# ============================================
# API CACHING
# ============================================
cache = {}
CACHE_TTL = 5

def get_cached_user(telegram_id):
    key = f"user_{telegram_id}"
    if key in cache:
        data, timestamp = cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return data
    return None

def set_cached_user(telegram_id, data):
    cache[f"user_{telegram_id}"] = (data, time.time())

def clear_user_cache(telegram_id):
    key = f"user_{telegram_id}"
    if key in cache:
        del cache[key]

# ============================================
# CORS CONFIGURATION
# ============================================
CORS(app, origins=["https://plant-usdt.vercel.app", "https://plantusdt.vercel.app"])

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'https://plant-usdt.vercel.app')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

db = DatabaseManager()
PROJECT_WALLET = Config.WALLET_ADDRESS

from services.deposit_scanner import DepositScanner
deposit_scanner = DepositScanner()

from services.task_system import (
    get_user_task_progress,
    check_task_conditions,
    claim_task_reward,
    get_task_stats,
    get_all_tasks,
    get_user_stats
)

# ============================================
# HELPER FUNCTION FOR WEBAPP PATH
# ============================================

def get_webapp_dir():
    """Get the absolute path to the webapp directory"""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'webapp')

# ============================================
# EXISTING ENDPOINTS
# ============================================

@app.route('/api/get_wallet', methods=['GET'])
def get_wallet():
    telegram_id = request.args.get('telegram_id', '0')
    if telegram_id == '0':
        return jsonify({'success': False, 'message': 'Missing telegram_id'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': True, 'wallet_address': ''})
        return jsonify({'success': True, 'wallet_address': user.wallet_address or ''})
    finally:
        session.close()

@app.route('/api/save_wallet', methods=['POST'])
def save_wallet():
    data = request.json
    telegram_id = data.get('telegram_id')
    wallet_address = data.get('wallet_address', '')
    
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        if not wallet_address:
            user.wallet_address = ''
            session.commit()
            clear_user_cache(telegram_id)
            return jsonify({'success': True, 'message': 'Wallet disconnected'})
        
        if not wallet_address.startswith('0x') or len(wallet_address) != 42:
            return jsonify({'success': False, 'message': 'Invalid wallet address'})
        
        if wallet_address.lower() == PROJECT_WALLET.lower():
            return jsonify({'success': False, 'message': 'This is the project wallet on Polygon. Please enter your own wallet address.'})
        
        user.wallet_address = wallet_address
        session.commit()
        clear_user_cache(telegram_id)
        return jsonify({'success': True, 'message': 'Wallet saved successfully'})
    finally:
        session.close()

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    telegram_id = data.get('telegram_id')
    
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid amount'})
    
    address = data.get('address')
    
    if not telegram_id or not amount or not address:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    if address.lower() == PROJECT_WALLET.lower():
        return jsonify({'success': False, 'message': 'Cannot withdraw to project wallet on Polygon. Please use your own wallet address.'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        if user.balance < amount:
            return jsonify({'success': False, 'message': f'Insufficient balance. Your balance is ${user.balance:.2f} USDT'})
        
        if amount < 2:
            return jsonify({'success': False, 'message': 'Minimum withdrawal is $2'})
        
        fee = amount * 0.10
        net_amount = amount - fee
        
        withdrawal = Withdrawal(
            user_id=user.id,
            amount=amount,
            fee=fee,
            net_amount=net_amount,
            wallet_address=address,
            status='pending'
        )
        session.add(withdrawal)
        
        user.balance -= amount
        
        session.commit()
        clear_user_cache(telegram_id)
        return jsonify({'success': True, 'message': 'Withdrawal request submitted'})
    finally:
        session.close()

@app.route('/api/get_referral_code', methods=['GET'])
def get_referral_code():
    telegram_id = request.args.get('telegram_id', '0')
    
    if telegram_id == '0':
        return jsonify({'success': False, 'message': 'User not found'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        return jsonify({
            'success': True,
            'referral_code': user.referral_code
        })
    finally:
        session.close()

@app.route('/api/referral_stats/<int:telegram_id>', methods=['GET'])
def get_referral_stats(telegram_id):
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        level1_refs = session.query(User).filter_by(referred_by=user.id).all()
        level1_count = len(level1_refs)
        level1_earnings = user.referral_deposit_earnings or 0
        
        return jsonify({
            'success': True,
            'level1_count': level1_count,
            'level1_earnings': level1_earnings,
            'total_referrals': level1_count,
            'total_earnings': level1_earnings
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

@app.route('/api/user', methods=['GET'])
def get_user():
    telegram_id = request.args.get('telegram_id', '0')
    
    if telegram_id == '0':
        return jsonify({
            'success': True,
            'balance': 0,
            'total_invested': 0,
            'total_deposited': 0,
            'fields': [],
            'referrals': 0,
            'referral_earned': 0,
            'investment_earnings': 0,
            'total_earnings': 0,
            'level1_count': 0,
            'total_ad_earnings': 0,
            'interstitial_ads_disabled': False,
            'has_received_welcome_bonus': False,
            'tasks_earnings': 0
        })
    
    cached = get_cached_user(telegram_id)
    if cached:
        return jsonify(cached)
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        
        if not user:
            response = {
                'success': True,
                'balance': 0,
                'total_invested': 0,
                'total_deposited': 0,
                'fields': [],
                'referrals': 0,
                'referral_earned': 0,
                'investment_earnings': 0,
                'total_earnings': 0,
                'level1_count': 0,
                'total_ad_earnings': 0,
                'interstitial_ads_disabled': False,
                'has_received_welcome_bonus': False,
                'tasks_earnings': 0
            }
            set_cached_user(telegram_id, response)
            return jsonify(response)
        
        investments = session.query(Investment).filter_by(user_id=user.id).all()
        fields = []
        for inv in investments:
            if inv.is_active or not inv.is_completed:
                fields.append({
                    'field_number': inv.field_number,
                    'amount': float(inv.amount),
                    'total_return': float(inv.expected_return),
                    'paid_out': float(inv.paid_out or 0),
                    'start_date': inv.start_date.isoformat(),
                    'is_active': inv.is_active,
                    'next_payout_date': None,
                    'lock_period': inv.lock_period,
                    'unlock_date': inv.unlock_date.isoformat() if inv.unlock_date else None,
                    'is_locked': inv.is_locked,
                    'expected_return': float(inv.expected_return)
                })
        
        level1_refs = session.query(User).filter_by(referred_by=user.id).all()
        level1_count = len(level1_refs)
        
        referral_earned = float((user.referral_earnings_all_time or 0) + (user.active_referral_bonus_earned or 0))
        investment_earnings = float(user.investment_earnings_all_time or 0)
        total_earnings = referral_earned + investment_earnings + float(user.total_ad_earnings or 0) + float(user.tasks_earnings or 0)
        
        response = {
            'success': True,
            'balance': round(float(user.balance or 0), 3),
            'total_invested': round(float(user.total_invested or 0), 3),
            'total_deposited': round(float(user.total_deposited or 0), 3),
            'fields': fields,
            'referrals': level1_count,
            'referral_earned': round(referral_earned, 3),
            'investment_earnings': round(investment_earnings, 3),
            'total_earnings': round(total_earnings, 3),
            'level1_count': level1_count,
            'total_ad_earnings': round(float(user.total_ad_earnings or 0), 3),
            'interstitial_ads_disabled': user.interstitial_ads_disabled or False,
            'has_received_welcome_bonus': user.has_received_welcome_bonus or False,
            'tasks_earnings': round(float(user.tasks_earnings or 0), 3)
        }
        
        set_cached_user(telegram_id, response)
        return jsonify(response)
    finally:
        session.close()

@app.route('/api/real_history', methods=['GET'])
def get_real_history():
    telegram_id = request.args.get('telegram_id', '0')
    
    if telegram_id == '0':
        return jsonify({'success': False, 'message': 'User not found'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        transactions = []
        
        deposits = session.query(Deposit).filter_by(user_id=user.id).all()
        for d in deposits:
            transactions.append({
                'type': 'deposit',
                'amount': round(float(d.amount), 3),
                'status': 'completed',
                'date': d.confirmed_at.strftime('%Y-%m-%d %H:%M')
            })
        
        payouts = session.query(DailyPayout).filter_by(user_id=user.id).all()
        for p in payouts:
            transactions.append({
                'type': 'earnings',
                'amount': round(float(p.amount), 3),
                'status': 'completed',
                'date': p.paid_at.strftime('%Y-%m-%d %H:%M')
            })
        
        referral_earnings = user.referral_deposit_earnings or 0
        if referral_earnings > 0:
            transactions.append({
                'type': 'referral_earnings',
                'amount': round(float(referral_earnings), 3),
                'status': 'completed',
                'date': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
            })
        
        if user.total_ad_earnings and user.total_ad_earnings > 0:
            transactions.append({
                'type': 'ad_earnings',
                'amount': round(float(user.total_ad_earnings), 3),
                'status': 'completed',
                'date': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
            })
        
        if user.tasks_earnings and user.tasks_earnings > 0:
            transactions.append({
                'type': 'tasks_earnings',
                'amount': round(float(user.tasks_earnings), 3),
                'status': 'completed',
                'date': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
            })
        
        withdrawals = session.query(Withdrawal).filter_by(user_id=user.id).all()
        for w in withdrawals:
            transactions.append({
                'type': 'withdraw',
                'amount': round(float(w.amount), 3),
                'status': w.status,
                'date': w.created_at.strftime('%Y-%m-%d %H:%M')
            })
        
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        return jsonify({'transactions': transactions})
    finally:
        session.close()

@app.route('/api/investments/<int:telegram_id>', methods=['GET'])
def get_investments(telegram_id):
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        investments = session.query(Investment).filter_by(user_id=user.id).all()
        transactions = []
        for inv in investments:
            transactions.append({
                'type': 'investment',
                'amount': round(float(inv.amount), 3),
                'status': 'active' if inv.is_active else 'completed',
                'date': inv.start_date.strftime('%Y-%m-%d %H:%M'),
                'field': inv.field_number,
                'paid_out': round(float(inv.paid_out or 0), 3),
                'total_return': round(float(inv.expected_return), 3)
            })
        
        return jsonify({'transactions': transactions})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

@app.route('/api/invest', methods=['POST'])
def invest():
    data = request.json
    telegram_id = data.get('telegram_id')
    field_number = data.get('field_number')
    amount = data.get('amount')
    
    if not telegram_id or not field_number or not amount:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        if user.balance < amount:
            return jsonify({'success': False, 'message': 'Insufficient balance'})
        
        if amount < 5 or amount > 100:
            return jsonify({'success': False, 'message': 'Amount must be between $5 and $100'})
        
        existing = session.query(Investment).filter_by(
            user_id=user.id,
            field_number=field_number,
            is_active=True
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': f'Field #{field_number} is already planted'})
        
        from config.settings import Config
        from datetime import datetime, timedelta
        total_return = amount * Config.DAILY_RATE * Config.INVESTMENT_DAYS
        now = datetime.utcnow()
        
        investment = Investment(
            user_id=user.id,
            field_number=field_number,
            amount=amount,
            total_return=total_return,
            end_date=now + timedelta(days=Config.INVESTMENT_DAYS),
            next_payout_date=now + timedelta(hours=24)
        )
        session.add(investment)
        
        user.balance -= amount
        user.total_invested += amount
        
        session.commit()
        clear_user_cache(telegram_id)
        
        return jsonify({
            'success': True,
            'message': f'Successfully invested ${amount} in Field #{field_number}'
        })
    finally:
        session.close()

@app.route('/api/invest_locked', methods=['POST'])
def invest_locked():
    data = request.json
    telegram_id = data.get('telegram_id')
    field_number = data.get('field_number')
    amount = data.get('amount')
    lock_period = data.get('lock_period', 30)
    
    if not telegram_id or not field_number or not amount or not lock_period:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    if lock_period not in [1, 7, 30]:
        return jsonify({'success': False, 'message': 'Lock period must be 1, 7, or 30 days'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        if user.balance < amount:
            return jsonify({'success': False, 'message': 'Insufficient balance'})
        
        if amount < 5 or amount > 100:
            return jsonify({'success': False, 'message': 'Amount must be between $5 and $100'})
        
        existing = session.query(Investment).filter_by(
            user_id=user.id,
            field_number=field_number,
            is_active=True
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': f'Field #{field_number} is already active'})
        
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        
        multipliers = {1: 1.02, 7: 1.18, 30: 1.80}
        multiplier = multipliers.get(lock_period, 1.80)
        expected_return = amount * multiplier
        unlock_date = now + timedelta(days=lock_period)
        
        investment = Investment(
            user_id=user.id,
            field_number=field_number,
            amount=amount,
            lock_period=lock_period,
            unlock_date=unlock_date,
            expected_return=expected_return,
            start_date=now,
            end_date=unlock_date,
            is_active=True,
            is_locked=True,
            completed_at=None,
            principal_returned=False
        )
        session.add(investment)
        
        user.balance -= amount
        user.total_invested += amount
        
        session.commit()
        clear_user_cache(telegram_id)
        
        return jsonify({
            'success': True,
            'message': f'Successfully invested ${amount} in Field #{field_number} on Polygon network',
            'lock_period': lock_period,
            'expected_return': expected_return,
            'unlock_date': unlock_date.isoformat()
        })
    finally:
        session.close()

@app.route('/api/check_deposit_with_amount', methods=['GET'])
def check_deposit_with_amount():
    telegram_id = request.args.get('telegram_id')
    expected_amount = request.args.get('expected_amount', type=float)
    
    if not telegram_id or not expected_amount:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    try:
        from telegram import Bot
        bot = Bot(token=Config.BOT_TOKEN)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        session = db.get_session()
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if user:
            session.query(PendingDepositCheck).filter_by(user_id=user.id).delete()
            pending = PendingDepositCheck(
                user_id=user.id,
                amount=expected_amount
            )
            session.add(pending)
            session.commit()
        session.close()
        
        result = loop.run_until_complete(
            deposit_scanner.check_deposit_with_amount(
                int(telegram_id),
                expected_amount,
                bot
            )
        )
        loop.close()
        
        if result and result.get('success'):
            clear_user_cache(telegram_id)
            return jsonify(result)
        else:
            return jsonify({'success': False, 'message': 'No new deposit found. Please wait a few minutes and try again.'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

# ============================================
# AD REWARD ENDPOINTS
# ============================================

@app.route('/api/can_watch_ad', methods=['GET'])
def can_watch_ad():
    return jsonify({'can_watch': True, 'watched_today': 0})

@app.route('/api/credit_ad_reward', methods=['POST'])
def credit_ad_reward():
    data = request.json
    telegram_id = data.get('telegram_id')
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        reward = 0.001
        user.balance += reward
        user.total_ads_watched = (user.total_ads_watched or 0) + 1
        user.total_ad_earnings = (user.total_ad_earnings or 0) + reward
        
        session.commit()
        clear_user_cache(telegram_id)
        return jsonify({
            'success': True,
            'reward': reward,
            'balance': user.balance
        })
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

# ============================================
# CLAIM INVESTMENT ENDPOINT
# ============================================

@app.route('/api/claim_investment', methods=['POST'])
def claim_investment():
    data = request.json
    telegram_id = data.get('telegram_id')
    field_number = data.get('field_number')
    
    if not telegram_id or not field_number:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        investment = session.query(Investment).filter_by(
            user_id=user.id,
            field_number=field_number,
            is_active=True,
            is_locked=True
        ).first()
        
        if not investment:
            return jsonify({'success': False, 'message': 'No locked investment found for this field'})
        
        now = datetime.utcnow()
        if investment.unlock_date > now:
            return jsonify({'success': False, 'message': 'Investment is not yet unlocked'})
        
        profit = investment.expected_return - investment.amount
        amount_to_credit = investment.expected_return
        
        investment.is_locked = False
        investment.is_active = False
        investment.is_completed = True
        investment.completed_at = now
        investment.principal_returned = True
        
        user.balance += amount_to_credit
        user.total_earned += profit
        user.investment_earnings_all_time = (user.investment_earnings_all_time or 0) + profit
        user.total_earnings_all_time = (user.total_earnings_all_time or 0) + profit
        
        payout = DailyPayout(
            user_id=user.id,
            investment_id=investment.id,
            amount=profit,
            day_number=investment.lock_period,
            paid_at=now
        )
        session.add(payout)
        
        session.commit()
        clear_user_cache(telegram_id)
        
        return jsonify({
            'success': True,
            'amount': amount_to_credit,
            'profit': profit,
            'message': f'Successfully claimed ${amount_to_credit:.2f} USDT from Field #{field_number}'
        })
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error claiming investment: {e}")
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

# ============================================
# REFERRAL UPGRADE ENDPOINTS
# ============================================

@app.route('/api/referral_tiers', methods=['GET'])
def get_referral_tiers():
    from services.referral import REFERRAL_TIERS
    return jsonify({
        'success': True,
        'tiers': REFERRAL_TIERS
    })

@app.route('/api/referral_stats_full/<int:telegram_id>', methods=['GET'])
def get_referral_stats_full(telegram_id):
    from services.referral import get_referral_stats
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        stats = get_referral_stats(user.id, session)
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

@app.route('/api/upgrade_tier', methods=['POST'])
def upgrade_tier():
    from services.referral import upgrade_referral_tier
    
    data = request.json
    telegram_id = data.get('telegram_id')
    tier = data.get('tier')
    
    if not telegram_id or not tier:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        success, msg = upgrade_referral_tier(user.id, tier, session)
        
        if success:
            clear_user_cache(telegram_id)
            return jsonify({
                'success': True,
                'message': msg,
                'new_tier': tier,
                'new_balance': user.balance
            })
        else:
            return jsonify({'success': False, 'message': msg})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

# ============================================
# NEW FEATURE ENDPOINTS
# ============================================

@app.route('/api/disable_interstitial_ads', methods=['POST'])
def disable_interstitial_ads():
    from datetime import datetime
    
    data = request.json
    telegram_id = data.get('telegram_id')
    
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        if user.interstitial_ads_disabled:
            return jsonify({'success': False, 'message': 'Interstitial ads already disabled'})
        
        if user.balance < 10:
            return jsonify({'success': False, 'message': f'Insufficient balance. Need $10.00 USDT (you have ${user.balance:.2f})'})
        
        user.balance -= 10
        user.interstitial_ads_disabled = True
        user.interstitial_disabled_at = datetime.utcnow()
        
        session.commit()
        clear_user_cache(telegram_id)
        
        return jsonify({
            'success': True,
            'message': 'Interstitial ads disabled! You will no longer see ads on button clicks.',
            'new_balance': user.balance
        })
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

@app.route('/api/get_active_referrals/<int:telegram_id>', methods=['GET'])
def get_active_referrals(telegram_id):
    from services.referral import get_active_referral_count, get_active_referral_list, is_referral_active
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        active_count = get_active_referral_count(user.id, session)
        active_list = get_active_referral_list(user.id, session)
        
        total_referrals = session.query(User).filter_by(referred_by=user.id).count()
        
        return jsonify({
            'success': True,
            'active_count': active_count,
            'total_referrals': total_referrals,
            'active_list': active_list
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

@app.route('/api/claim_welcome_bonus', methods=['POST'])
def claim_welcome_bonus():
    from services.referral import award_welcome_bonus
    
    data = request.json
    telegram_id = data.get('telegram_id')
    
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        success, msg = award_welcome_bonus(user.id, session)
        
        if success:
            clear_user_cache(telegram_id)
            return jsonify({
                'success': True,
                'message': msg,
                'new_balance': user.balance
            })
        else:
            return jsonify({'success': False, 'message': msg})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

@app.route('/api/get_tasks/<int:telegram_id>', methods=['GET'])
def get_tasks(telegram_id):
    from services.referral import get_user_tasks as get_referral_tasks
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        tasks = get_referral_tasks(user.id, session)
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'completed_count': sum(1 for task in tasks.values() if task['completed']),
            'total_count': len(tasks)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

# ============================================
# TASK SYSTEM ENDPOINTS
# ============================================

@app.route('/api/tasks/<int:telegram_id>', methods=['GET'])
def api_get_tasks(telegram_id):
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        completed = check_task_conditions(user, session)
        
        tasks = get_user_task_progress(user.id, session, include_hidden=False)
        stats = get_task_stats(user.id, session)
        user_stats = get_user_stats(user, session)
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'stats': stats,
            'user_stats': user_stats,
            'newly_completed': [t["id"] for t in completed]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

@app.route('/api/claim_task_reward', methods=['POST'])
def api_claim_task_reward():
    data = request.json
    telegram_id = data.get('telegram_id')
    task_id = data.get('task_id')
    
    if not telegram_id or not task_id:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        success, msg = claim_task_reward(user.id, task_id, session)
        
        if success:
            clear_user_cache(telegram_id)
            return jsonify({
                'success': True,
                'message': msg,
                'new_balance': user.balance
            })
        else:
            return jsonify({'success': False, 'message': msg})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

@app.route('/api/task_stats/<int:telegram_id>', methods=['GET'])
def api_task_stats(telegram_id):
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        stats = get_task_stats(user.id, session)
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

# ============================================
# TASK MANAGEMENT ENDPOINTS
# ============================================

@app.route('/api/get_user_tasks/<int:telegram_id>', methods=['GET'])
def api_get_user_tasks(telegram_id):
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        tasks = get_user_task_progress(user.id, session, include_hidden=False)
        return jsonify({
            'success': True,
            'tasks': tasks
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

@app.route('/api/complete_task', methods=['POST'])
def api_complete_task():
    data = request.json
    telegram_id = data.get('telegram_id')
    task_id = data.get('task_id')
    
    if not telegram_id or not task_id:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        success, msg = complete_task(user.id, task_id, session)
        
        if success:
            clear_user_cache(telegram_id)
            return jsonify({'success': True, 'message': msg})
        else:
            return jsonify({'success': False, 'message': msg})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

@app.route('/api/claim_task_reward_old', methods=['POST'])
def api_claim_task_reward_old():
    data = request.json
    telegram_id = data.get('telegram_id')
    task_id = data.get('task_id')
    
    if not telegram_id or not task_id:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        success, msg = claim_task_reward(user.id, task_id, session)
        
        if success:
            clear_user_cache(telegram_id)
            return jsonify({
                'success': True,
                'message': msg,
                'new_balance': user.balance
            })
        else:
            return jsonify({'success': False, 'message': msg})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        session.close()

# ============================================
# SERVE STATIC FILES
# ============================================

@app.route('/deposit')
def deposit_page():
    return send_from_directory(get_webapp_dir(), 'deposit_new.html')

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(os.path.join(get_webapp_dir(), 'js'), filename)

@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(os.path.join(get_webapp_dir(), 'css'), filename)

@app.route('/<path:filename>')
def serve_static(filename):
    if filename.startswith('api/'):
        return jsonify({'success': False, 'message': 'Not found'}), 404
    return send_from_directory(get_webapp_dir(), filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=5001)

import sys
import os
import asyncio
import time
import logging
import random
import string
import math
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps
from collections import defaultdict

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Config FIRST
from config.settings import Config

from flask import Flask, jsonify, request, send_from_directory, session
from flask_session import Session

from database.db_manager import DatabaseManager
from database.models import User, Withdrawal, Investment, Deposit, DailyPayout, PendingDepositCheck, AuditLog, AdLog
from sqlalchemy import func

app = Flask(__name__)
logger = logging.getLogger(__name__)

# ============================================
# SESSION CONFIGURATION
# ============================================
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

Session(app)

# ============================================
# RATE LIMITING
# ============================================
rate_limits = defaultdict(list)
RATE_LIMIT = 160  # requests per minute
RATE_WINDOW = 60  # seconds

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        now = time.time()
        rate_limits[client_ip] = [t for t in rate_limits[client_ip] if now - t < RATE_WINDOW]
        if len(rate_limits[client_ip]) >= RATE_LIMIT:
            return jsonify({'success': False, 'message': 'Too many requests. Please wait.'}), 429
        rate_limits[client_ip].append(now)
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# SECURITY HEADERS
# ============================================
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['TRAP_BAD_REQUEST_ERRORS'] = True
app.config['TRAP_HTTP_EXCEPTIONS'] = True

@app.after_request
def security_headers(response):
    response.headers['Server'] = 'PlantUSDT'
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

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

def get_webapp_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'webapp')

# ============================================
# AUTHENTICATION HELPER
# ============================================
def get_authenticated_user(telegram_id):
    if not telegram_id or telegram_id == '0':
        return None, jsonify({'success': False, 'message': 'User not authenticated'}), 401
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return None, jsonify({'success': False, 'message': 'User not found'}), 404
        return user, None, None
    finally:
        session_db.close()

def sanitize_input(value):
    if value is None:
        return None
    return str(value).strip()

# ============================================
# MATH CAPTCHA
# ============================================
def generate_math_captcha():
    """Generate a simple math captcha question and answer"""
    num1 = random.randint(1, 20)
    num2 = random.randint(1, 20)
    operator = random.choice(['+', '-', '*'])
    
    if operator == '+':
        answer = num1 + num2
    elif operator == '-':
        answer = num1 - num2
    else:
        answer = num1 * num2
    
    question = f"{num1} {operator} {num2} = ?"
    return question, answer

def reset_daily_ad_count(user):
    """Reset daily ad count if a new day has started"""
    if not user.last_ad_reset:
        user.last_ad_reset = datetime.utcnow()
        user.daily_ad_count = 0
        clear_user_cache(user.telegram_id)
        return True
    
    now = datetime.utcnow()
    if now.date() > user.last_ad_reset.date():
        user.daily_ad_count = 0
        user.last_ad_reset = now
        clear_user_cache(user.telegram_id)
        return True
    return False

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/api/get_wallet', methods=['GET'])
@rate_limit
def get_wallet():
    telegram_id = sanitize_input(request.args.get('telegram_id', '0'))
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': True, 'wallet_address': ''})
        return jsonify({'success': True, 'wallet_address': user.wallet_address or ''})
    finally:
        session_db.close()

@app.route('/api/save_wallet', methods=['POST'])
@rate_limit
def save_wallet():
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    wallet_address = sanitize_input(data.get('wallet_address', ''))
    
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        if not wallet_address:
            user.wallet_address = ''
            session_db.commit()
            clear_user_cache(telegram_id)
            return jsonify({'success': True, 'message': 'Wallet disconnected'})
        
        if not wallet_address.startswith('0x') or len(wallet_address) != 42:
            return jsonify({'success': False, 'message': 'Invalid wallet address'}), 400
        
        if wallet_address.lower() == PROJECT_WALLET.lower():
            return jsonify({'success': False, 'message': 'This is the project wallet. Please enter your own wallet address.'}), 400
        
        user.wallet_address = wallet_address
        session_db.commit()
        clear_user_cache(telegram_id)
        return jsonify({'success': True, 'message': 'Wallet saved successfully'})
    finally:
        session_db.close()

@app.route('/api/withdraw', methods=['POST'])
@rate_limit
def withdraw():
    from decimal import Decimal
    from datetime import datetime, timedelta
    import math
    
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid amount'}), 400
    
    address = sanitize_input(data.get('address'))
    
    if not telegram_id or not amount or not address:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    if address.lower() == PROJECT_WALLET.lower():
        return jsonify({'success': False, 'message': 'Cannot withdraw to project wallet. Please use your own wallet address.'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Check for existing pending withdrawal
        existing_pending = session_db.query(Withdrawal).filter_by(
            user_id=user.id,
            status='pending'
        ).first()
        
        if existing_pending:
            return jsonify({
                'success': False,
                'message': 'You already have a pending withdrawal. Please wait for it to be processed before submitting another one.'
            }), 400
        
        # ---- COOLDOWN CHECK ----
        if user.last_withdrawal_at:
            time_since_last = (datetime.utcnow() - user.last_withdrawal_at).total_seconds()
            if time_since_last < 86400:
                remaining = int(86400 - time_since_last)
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                seconds = remaining % 60
                time_str = f"{hours}h {minutes}m {seconds}s"
                return jsonify({
                    'success': False,
                    'message': f'You can withdraw again in {time_str}',
                    'cooldown_remaining': remaining
                }), 400
        
        if user.balance < amount:
            return jsonify({'success': False, 'message': f'Insufficient balance. Your balance is ${user.balance:.2f} USDT'}), 400
        
        # ---- FULL BALANCE ONLY ----
        # Allow small tolerance for floating point issues (0.001)
        if abs(amount - float(user.balance)) > 0.001:
            return jsonify({
                'success': False,
                'message': f'You can only withdraw your full balance (${float(user.balance):.2f}). Partial withdrawals are not allowed.'
            }), 400
        
        # ---- TRUNCATE TO 2 DECIMAL PLACES (FLOOR) ----
        # User can withdraw the floored amount, dust remains in balance
        withdraw_amount = math.floor(amount * 100) / 100
        dust = amount - withdraw_amount
        
        # Keep dust in user's balance
        user.balance = Decimal(str(dust))
        
        if withdraw_amount < 1:
            return jsonify({'success': False, 'message': 'Minimum withdrawal is $1'}), 400
        
        # Use withdraw_amount for the rest of the withdrawal process
        amount = withdraw_amount
        
        # Calculate fee (percentage only - no flat fees)
        fee_percent = 0.0

        if amount < 10:
            fee_percent = 0.05
        elif amount < 30:
            fee_percent = 0.10
        elif amount < 50:
            fee_percent = 0.15
        elif amount < 100:
            fee_percent = 0.20
        else:
            fee_percent = 0.25

        fee = amount * fee_percent
        net_amount = amount - fee
        
        withdrawal = Withdrawal(
            user_id=user.id,
            amount=amount,
            fee=fee,
            net_amount=net_amount,
            wallet_address=address,
            status='pending'
        )
        session_db.add(withdrawal)
        
        # Log to audit log
        audit = AuditLog(
            user_id=user.id,
            action='withdrawal_request',
            field_changed='balance',
            old_value=float(user.balance + Decimal(str(amount)) + Decimal(str(dust))),
            new_value=float(user.balance),
            amount=float(amount),
            description=f'Withdrawal request of ${amount:.2f} to {address[:10]}... (dust: ${dust:.3f})',
            source='user',
            created_at=datetime.utcnow()
        )
        session_db.add(audit)
        
        session_db.commit()
        clear_user_cache(telegram_id)
        return jsonify({'success': True, 'message': 'Withdrawal request submitted'})
    finally:
        session_db.close()

@app.route('/api/get_referral_code', methods=['GET'])
@rate_limit
def get_referral_code():
    telegram_id = sanitize_input(request.args.get('telegram_id', '0'))
    if telegram_id == '0':
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        return jsonify({
            'success': True,
            'referral_code': user.referral_code
        })
    finally:
        session_db.close()

@app.route('/api/referral_stats/<int:telegram_id>', methods=['GET'])
@rate_limit
def get_referral_stats(telegram_id):
    user, err_response, status = get_authenticated_user(str(telegram_id))
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        level1_refs = session_db.query(User).filter_by(referred_by=user.id).all()
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
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/user', methods=['GET'])
@rate_limit
def get_user():
    telegram_id = sanitize_input(request.args.get('telegram_id', '0'))
    
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
            'tasks_earnings': 0,
            'referral_tier': 'free',
            'expected_daily_earnings': 0,
            'last_withdrawal_at': None,
            'daily_ad_count': 0
        })
    
    cached = get_cached_user(telegram_id)
    if cached:
        return jsonify(cached)
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
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
                'tasks_earnings': 0,
                'referral_tier': 'free',
                'expected_daily_earnings': 0,
                'last_withdrawal_at': None,
                'daily_ad_count': 0
            }
            set_cached_user(telegram_id, response)
            return jsonify(response)
        
        # Check if it's a new day and invalidate cache if needed
        if user and user.last_ad_reset:
            now = datetime.utcnow()
            if now.date() > user.last_ad_reset.date():
                clear_user_cache(telegram_id)
        
        investments = session_db.query(Investment).filter_by(user_id=user.id).all()
        fields = []
        expected_daily_earnings = 0.0
        
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
                
                # Calculate expected daily earnings for active locked investments
                if inv.is_active and inv.is_locked and inv.lock_period > 0:
                    profit = float(inv.expected_return) - float(inv.amount)
                    daily = profit / inv.lock_period
                    expected_daily_earnings += daily
        
        level1_refs = session_db.query(User).filter_by(referred_by=user.id).all()
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
            'tasks_earnings': round(float(user.tasks_earnings or 0), 3),
            'referral_tier': user.referral_tier or 'free',
            'expected_daily_earnings': round(expected_daily_earnings, 2),
            'last_withdrawal_at': user.last_withdrawal_at.isoformat() if user.last_withdrawal_at else None,
            'daily_ad_count': user.daily_ad_count or 0
        }
        
        set_cached_user(telegram_id, response)
        return jsonify(response)
    finally:
        session_db.close()

@app.route('/api/real_history', methods=['GET'])
@rate_limit
def get_real_history():
    telegram_id = sanitize_input(request.args.get('telegram_id', '0'))
    if telegram_id == '0':
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        transactions = []
        
        deposits = session_db.query(Deposit).filter_by(user_id=user.id).all()
        for d in deposits:
            transactions.append({
                'type': 'deposit',
                'amount': round(float(d.amount), 3),
                'status': 'completed',
                'date': d.confirmed_at.strftime('%Y-%m-%d %H:%M')
            })
        
        payouts = session_db.query(DailyPayout).filter_by(user_id=user.id).all()
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
        
        withdrawals = session_db.query(Withdrawal).filter_by(user_id=user.id).all()
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
        session_db.close()

@app.route('/api/investments/<int:telegram_id>', methods=['GET'])
@rate_limit
def get_investments(telegram_id):
    user, err_response, status = get_authenticated_user(str(telegram_id))
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        investments = session_db.query(Investment).filter_by(user_id=user.id).all()
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
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/invest', methods=['POST'])
@rate_limit
def invest():
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    field_number = data.get('field_number')
    amount = data.get('amount')
    
    if not telegram_id or not field_number or not amount:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        if user.balance < amount:
            return jsonify({'success': False, 'message': 'Insufficient balance'}), 400
        
        if amount < 5 or amount > 100:
            return jsonify({'success': False, 'message': 'Amount must be between $5 and $100'}), 400
        
        existing = session_db.query(Investment).filter_by(
            user_id=user.id,
            field_number=field_number,
            is_active=True
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': f'Field #{field_number} is already planted'}), 400
        
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
        session_db.add(investment)
        user.balance -= amount
        user.total_invested += amount
        session_db.commit()
        clear_user_cache(telegram_id)
        
        return jsonify({
            'success': True,
            'message': f'Successfully invested ${amount} in Field #{field_number}'
        })
    finally:
        session_db.close()

@app.route('/api/invest_locked', methods=['POST'])
@rate_limit
def invest_locked():
    from decimal import Decimal
    
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    field_number = data.get('field_number')
    amount = data.get('amount')
    lock_period = data.get('lock_period', 30)
    
    if not telegram_id or not field_number or not amount or not lock_period:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    if lock_period not in [1, 7, 30]:
        return jsonify({'success': False, 'message': 'Lock period must be 1, 7, or 30 days'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        if user.balance < amount:
            return jsonify({'success': False, 'message': 'Insufficient balance'}), 400
        
        if amount < 5 or amount > 100:
            return jsonify({'success': False, 'message': 'Amount must be between $5 and $100'}), 400
        
        existing = session_db.query(Investment).filter_by(
            user_id=user.id,
            field_number=field_number,
            is_active=True
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': f'Field #{field_number} is already active'}), 400
        
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
        session_db.add(investment)
        
        user.balance -= Decimal(str(amount))
        
        session_db.commit()
        clear_user_cache(telegram_id)
        
        return jsonify({
            'success': True,
            'message': f'Successfully invested ${amount} in Field #{field_number} on Polygon network',
            'lock_period': lock_period,
            'expected_return': expected_return,
            'unlock_date': unlock_date.isoformat()
        })
    except Exception as e:
        session_db.rollback()
        logger.error(f"Error in invest_locked: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/check_deposit_with_amount', methods=['GET'])
@rate_limit
def check_deposit_with_amount():
    telegram_id = sanitize_input(request.args.get('telegram_id'))
    expected_amount = request.args.get('expected_amount', type=float)
    
    if not telegram_id or not expected_amount:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    try:
        from telegram import Bot
        bot = Bot(token=Config.BOT_TOKEN)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        session_db = db.get_session()
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if user:
            session_db.query(PendingDepositCheck).filter_by(user_id=user.id).delete()
            pending = PendingDepositCheck(
                user_id=user.id,
                amount=expected_amount
            )
            session_db.add(pending)
            session_db.commit()
        session_db.close()
        
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
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/can_watch_ad', methods=['GET'])
@rate_limit
def can_watch_ad():
    return jsonify({'can_watch': True, 'watched_today': 0})

@app.route('/api/credit_ad_reward', methods=['POST'])
@rate_limit
def credit_ad_reward():
    from decimal import Decimal
    from datetime import datetime
    
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'}), 400
    
    # Verify math captcha
    captcha_answer = data.get('captcha_answer')
    captcha_question = data.get('captcha_question')
    
    if not captcha_answer or not captcha_question:
        return jsonify({
            'success': False, 
            'message': 'Please solve the math question to earn ad reward.',
            'need_captcha': True
        }), 400
    
    # Validate captcha
    try:
        expected_answer = int(captcha_answer)
    except ValueError:
        return jsonify({
            'success': False,
            'message': 'Invalid captcha answer.',
            'need_captcha': True
        }), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Check if user is flagged for anomaly
        if user.flagged_for_anomaly:
            return jsonify({
                'success': False,
                'message': 'Your account has been flagged for suspicious activity. Please contact support.'
            }), 403
        
        # Reset daily ad count if new day (this clears cache)
        reset_daily_ad_count(user)
        
        # ANTI-ABUSE: Max 50 ads per day
        if user.daily_ad_count >= 50:
            return jsonify({
                'success': False,
                'message': 'You have reached the daily ad limit (50 ads per day). Come back tomorrow!'
            }), 400
        
        # ANTI-ABUSE: Device fingerprint tracking
        fingerprint = data.get('device_fingerprint', 'unknown')
        if fingerprint != 'unknown' and user.device_fingerprint and user.device_fingerprint != fingerprint:
            # Same user, different device fingerprint - flag for review
            user.flagged_for_anomaly = True
            session_db.commit()
            logger.warning(f"⚠️ User {user.telegram_id} has multiple device fingerprints: {user.device_fingerprint} vs {fingerprint}")
        
        if not user.device_fingerprint and fingerprint != 'unknown':
            user.device_fingerprint = fingerprint
        
        reward = Decimal('0.001')
        old_balance = Decimal(user.balance or 0)
        old_ad_earnings = Decimal(user.total_ad_earnings or 0)
        old_total_earnings = Decimal(user.total_earnings_all_time or 0)
        
        user.balance = (user.balance or Decimal('0')) + reward
        user.total_ads_watched = (user.total_ads_watched or 0) + 1
        user.total_ad_earnings = (user.total_ad_earnings or Decimal('0')) + reward
        user.total_earnings_all_time = (user.total_earnings_all_time or Decimal('0')) + reward
        user.daily_ad_count = (user.daily_ad_count or 0) + 1
        
        # Log ad watch
        ad_log = AdLog(
            user_id=user.id,
            watched_at=datetime.utcnow(),
            reward=reward,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', 'unknown'),
            session_id=request.headers.get('X-Telegram-WebApp-Session', 'unknown')
        )
        session_db.add(ad_log)
        
        # Log to audit log
        audit = AuditLog(
            user_id=user.id,
            action='ad_earnings',
            field_changed='balance',
            old_value=float(old_balance),
            new_value=float(user.balance),
            amount=float(reward),
            description=f'Ad reward #{user.total_ads_watched} (day {user.daily_ad_count}/50)',
            source='ad_reward',
            created_at=datetime.utcnow()
        )
        session_db.add(audit)
        
        session_db.commit()
        clear_user_cache(telegram_id)
        return jsonify({
            'success': True,
            'reward': float(reward),
            'balance': float(user.balance),
            'daily_ad_count': user.daily_ad_count,
            'daily_ad_limit': 50,
            'total_ad_earnings': float(user.total_ad_earnings)
        })
    except Exception as e:
        session_db.rollback()
        logger.error(f"Error crediting ad reward: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/claim_investment', methods=['POST'])
@rate_limit
def claim_investment():
    from decimal import Decimal
    
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    field_number = data.get('field_number')
    
    if not telegram_id or not field_number:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        investment = session_db.query(Investment).filter_by(
            user_id=user.id,
            field_number=field_number,
            is_active=True,
            is_locked=True
        ).first()
        
        if not investment:
            return jsonify({'success': False, 'message': 'No locked investment found for this field'}), 404
        
        now = datetime.utcnow()
        if investment.unlock_date > now:
            return jsonify({'success': False, 'message': 'Investment is not yet unlocked'}), 400
        
        profit = Decimal(str(investment.expected_return)) - Decimal(str(investment.amount))
        amount_to_credit = Decimal(str(investment.expected_return))
        old_balance = Decimal(user.balance or 0)
        old_investment_earnings = Decimal(user.investment_earnings_all_time or 0)
        old_total_earnings = Decimal(user.total_earnings_all_time or 0)
        
        investment.is_locked = False
        investment.is_active = False
        investment.is_completed = True
        investment.completed_at = now
        investment.principal_returned = True
        
        user.balance = (user.balance or Decimal('0')) + amount_to_credit
        user.total_earned = (user.total_earned or Decimal('0')) + profit
        user.investment_earnings_all_time = (user.investment_earnings_all_time or Decimal('0')) + profit
        user.total_earnings_all_time = (user.total_earnings_all_time or Decimal('0')) + profit
        
        payout = DailyPayout(
            user_id=user.id,
            investment_id=investment.id,
            amount=float(profit),
            day_number=investment.lock_period,
            paid_at=now
        )
        session_db.add(payout)
        
        # Log to audit log
        audit = AuditLog(
            user_id=user.id,
            action='investment_claim',
            field_changed='balance',
            old_value=float(old_balance),
            new_value=float(user.balance),
            amount=float(amount_to_credit),
            description=f'Claimed Field #{field_number} ({investment.lock_period} days)',
            source='investment',
            created_at=datetime.utcnow()
        )
        session_db.add(audit)
        
        session_db.commit()
        clear_user_cache(telegram_id)
        
        return jsonify({
            'success': True,
            'amount': float(amount_to_credit),
            'profit': float(profit),
            'message': f'Successfully claimed ${amount_to_credit:.2f} USDT from Field #{field_number}'
        })
        
    except Exception as e:
        session_db.rollback()
        logger.error(f"Error claiming investment: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/total_withdrawn/<int:telegram_id>', methods=['GET'])
@rate_limit
def total_withdrawn(telegram_id):
    user, err_response, status = get_authenticated_user(str(telegram_id))
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        total = session_db.query(func.sum(Withdrawal.amount)).filter_by(user_id=user.id, status='completed').scalar() or 0
        return jsonify({'success': True, 'total_withdrawn': float(total)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/referral_tiers', methods=['GET'])
@rate_limit
def get_referral_tiers():
    from services.referral import REFERRAL_TIERS
    return jsonify({
        'success': True,
        'tiers': REFERRAL_TIERS
    })

@app.route('/api/referral_stats_full/<int:telegram_id>', methods=['GET'])
@rate_limit
def get_referral_stats_full(telegram_id):
    user, err_response, status = get_authenticated_user(str(telegram_id))
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        from services.referral import get_referral_stats
        stats = get_referral_stats(user.id, session_db)
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/upgrade_tier', methods=['POST'])
@rate_limit
def upgrade_tier():
    from services.referral import upgrade_referral_tier
    
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    tier = sanitize_input(data.get('tier'))
    
    if not telegram_id or not tier:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        success, msg = upgrade_referral_tier(user.id, tier, session_db)
        
        if success:
            clear_user_cache(telegram_id)
            return jsonify({
                'success': True,
                'message': msg,
                'new_tier': tier,
                'new_balance': user.balance
            })
        else:
            return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/disable_interstitial_ads', methods=['POST'])
@rate_limit
def disable_interstitial_ads():
    from decimal import Decimal
    from datetime import datetime
    
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        if user.interstitial_ads_disabled:
            return jsonify({'success': False, 'message': 'Interstitial ads already disabled'}), 400
        
        cost = Decimal('4')
        old_balance = Decimal(user.balance or 0)
        
        if user.balance < cost:
            return jsonify({'success': False, 'message': f'Insufficient balance. Need $4.00 USDT (you have ${user.balance:.2f})'}), 400
        
        user.balance = (user.balance or Decimal('0')) - cost
        user.interstitial_ads_disabled = True
        user.interstitial_disabled_at = datetime.utcnow()
        
        # Log to audit log
        audit = AuditLog(
            user_id=user.id,
            action='disable_ads',
            field_changed='balance',
            old_value=float(old_balance),
            new_value=float(user.balance),
            amount=float(cost),
            description='Disabled interstitial ads',
            source='user',
            created_at=datetime.utcnow()
        )
        session_db.add(audit)
        
        session_db.commit()
        clear_user_cache(telegram_id)
        
        return jsonify({
            'success': True,
            'message': 'Interstitial ads disabled! You will no longer see ads on button clicks.',
            'new_balance': float(user.balance)
        })
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/get_active_referrals/<int:telegram_id>', methods=['GET'])
@rate_limit
def get_active_referrals(telegram_id):
    user, err_response, status = get_authenticated_user(str(telegram_id))
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        from services.referral import get_active_referral_count, get_active_referral_list
        active_count = get_active_referral_count(user.id, session_db)
        active_list = get_active_referral_list(user.id, session_db)
        total_referrals = session_db.query(User).filter_by(referred_by=user.id).count()
        
        return jsonify({
            'success': True,
            'active_count': active_count,
            'total_referrals': total_referrals,
            'active_list': active_list
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/claim_welcome_bonus', methods=['POST'])
@rate_limit
def claim_welcome_bonus():
    from services.referral import award_welcome_bonus
    
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        success, msg = award_welcome_bonus(user.id, session_db)
        
        if success:
            clear_user_cache(telegram_id)
            return jsonify({
                'success': True,
                'message': msg,
                'new_balance': user.balance
            })
        else:
            return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/get_tasks/<int:telegram_id>', methods=['GET'])
@rate_limit
def get_tasks(telegram_id):
    user, err_response, status = get_authenticated_user(str(telegram_id))
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        from services.referral import get_user_tasks as get_referral_tasks
        tasks = get_referral_tasks(user.id, session_db)
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'completed_count': sum(1 for task in tasks.values() if task['completed']),
            'total_count': len(tasks)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/tasks/<int:telegram_id>', methods=['GET'])
@rate_limit
def api_get_tasks(telegram_id):
    user, err_response, status = get_authenticated_user(str(telegram_id))
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        completed = check_task_conditions(user, session_db)
        tasks = get_user_task_progress(user.id, session_db, include_hidden=False)
        stats = get_task_stats(user.id, session_db)
        user_stats = get_user_stats(user, session_db)
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'stats': stats,
            'user_stats': user_stats,
            'newly_completed': [t["id"] for t in completed]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/claim_task_reward', methods=['POST'])
@rate_limit
def api_claim_task_reward():
    from decimal import Decimal
    
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    task_id = data.get('task_id')
    
    if not telegram_id or not task_id:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        success, msg = claim_task_reward(user.id, task_id, session_db)
        
        if success:
            clear_user_cache(telegram_id)
            return jsonify({
                'success': True,
                'message': msg,
                'new_balance': float(user.balance)
            })
        else:
            return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/task_stats/<int:telegram_id>', methods=['GET'])
@rate_limit
def api_task_stats(telegram_id):
    user, err_response, status = get_authenticated_user(str(telegram_id))
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        stats = get_task_stats(user.id, session_db)
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/get_user_tasks/<int:telegram_id>', methods=['GET'])
@rate_limit
def api_get_user_tasks(telegram_id):
    user, err_response, status = get_authenticated_user(str(telegram_id))
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        tasks = get_user_task_progress(user.id, session_db, include_hidden=False)
        return jsonify({
            'success': True,
            'tasks': tasks
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/complete_task', methods=['POST'])
@rate_limit
def api_complete_task():
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    task_id = data.get('task_id')
    
    if not telegram_id or not task_id:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        from services.task_manager import complete_task
        success, msg = complete_task(user.id, task_id, session_db)
        
        if success:
            clear_user_cache(telegram_id)
            return jsonify({'success': True, 'message': msg})
        else:
            return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

@app.route('/api/claim_task_reward_old', methods=['POST'])
@rate_limit
def api_claim_task_reward_old():
    from decimal import Decimal
    
    data = request.json
    telegram_id = sanitize_input(data.get('telegram_id'))
    task_id = data.get('task_id')
    
    if not telegram_id or not task_id:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    user, err_response, status = get_authenticated_user(telegram_id)
    if err_response:
        return err_response, status
    
    session_db = db.get_session()
    try:
        user = session_db.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        success, msg = claim_task_reward(user.id, task_id, session_db)
        
        if success:
            clear_user_cache(telegram_id)
            return jsonify({
                'success': True,
                'message': msg,
                'new_balance': float(user.balance)
            })
        else:
            return jsonify({'success': False, 'message': msg}), 400
    except Exception as e:
        session_db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        session_db.close()

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

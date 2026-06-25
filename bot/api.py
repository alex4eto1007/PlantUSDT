from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from database.models import User, Withdrawal, Investment, Deposit, DailyPayout
from sqlalchemy import func
from datetime import datetime

app = Flask(__name__)

# Configure CORS properly - single header with specific origins
CORS(app, origins=["https://plant-usdt.vercel.app", "https://plantusdt.vercel.app"])

# Add CORS headers to every response (single header)
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'https://plant-usdt.vercel.app')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

db = DatabaseManager()

# Project wallet - blocked from user use
PROJECT_WALLET = '0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76'

# Import deposit scanner for amount-based detection
from services.deposit_scanner import DepositScanner
deposit_scanner = DepositScanner()

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
        
        # If empty, disconnect
        if not wallet_address:
            user.wallet_address = ''
            session.commit()
            return jsonify({'success': True, 'message': 'Wallet disconnected'})
        
        # Validate
        if not wallet_address.startswith('0x') or len(wallet_address) != 42:
            return jsonify({'success': False, 'message': 'Invalid wallet address'})
        
        # Block project wallet
        if wallet_address.lower() == PROJECT_WALLET.lower():
            return jsonify({'success': False, 'message': 'This is the project wallet on Polygon. Please enter your own wallet address.'})
        
        user.wallet_address = wallet_address
        session.commit()
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
    
    # Block withdrawal to project wallet
    if address.lower() == PROJECT_WALLET.lower():
        return jsonify({'success': False, 'message': 'Cannot withdraw to project wallet on Polygon. Please use your own wallet address.'})
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        # Check balance
        if user.balance < amount:
            return jsonify({'success': False, 'message': f'Insufficient balance. Your balance is ${user.balance:.2f} USDT'})
        
        if amount < 2:
            return jsonify({'success': False, 'message': 'Minimum withdrawal is $2'})
        
        # Calculate fee and net amount
        fee = amount * 0.10
        net_amount = amount - fee
        
        # Create withdrawal
        withdrawal = Withdrawal(
            user_id=user.id,
            amount=amount,
            fee=fee,
            net_amount=net_amount,
            wallet_address=address,
            status='pending'
        )
        session.add(withdrawal)
        
        # Deduct from balance
        user.balance -= amount
        
        session.commit()
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
    """Get referral statistics - single level only"""
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        # Level 1 referrals only (no multi-tier)
        level1_refs = session.query(User).filter_by(referred_by=user.id).all()
        level1_count = len(level1_refs)
        
        # Get earnings from the referrer's deposit earnings
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
            'level2_count': 0
        })
    
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        
        if not user:
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
                'level2_count': 0
            })
        
        # Get investments (locked investments)
        investments = session.query(Investment).filter_by(user_id=user.id).all()
        fields = []
        for inv in investments:
            if inv.is_active or not inv.is_completed:
                fields.append({
                    'field_number': inv.field_number,
                    'amount': inv.amount,
                    'total_return': inv.expected_return,
                    'paid_out': inv.paid_out or 0,
                    'start_date': inv.start_date.isoformat(),
                    'is_active': inv.is_active,
                    'next_payout_date': None,
                    'lock_period': inv.lock_period,
                    'unlock_date': inv.unlock_date.isoformat() if inv.unlock_date else None,
                    'is_locked': inv.is_locked,
                    'expected_return': inv.expected_return
                })
        
        # Get referrals (level 1 only for display)
        level1_refs = session.query(User).filter_by(referred_by=user.id).all()
        level1_count = len(level1_refs)
        level2_count = 0
        
        referral_earned = user.referral_earnings_all_time or 0
        investment_earnings = user.investment_earnings_all_time or 0
        total_earnings = referral_earned + investment_earnings
        
        return jsonify({
            'success': True,
            'balance': user.balance,
            'total_invested': user.total_invested or 0,
            'total_deposited': user.total_deposited or 0,
            'fields': fields,
            'referrals': level1_count,
            'referral_earned': referral_earned,
            'investment_earnings': investment_earnings,
            'total_earnings': total_earnings,
            'level1_count': level1_count,
            'level2_count': level2_count
        })
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
        
        # Get deposits
        deposits = session.query(Deposit).filter_by(user_id=user.id).all()
        for d in deposits:
            transactions.append({
                'type': 'deposit',
                'amount': d.amount,
                'status': 'completed',
                'date': d.confirmed_at.strftime('%Y-%m-%d %H:%M')
            })
        
        # Get earnings (DailyPayout records - includes unlocks)
        payouts = session.query(DailyPayout).filter_by(user_id=user.id).all()
        for p in payouts:
            transactions.append({
                'type': 'earnings',
                'amount': p.amount,
                'status': 'completed',
                'date': p.paid_at.strftime('%Y-%m-%d %H:%M')
            })
        
        # Get referral earnings
        referral_earnings = user.referral_deposit_earnings or 0
        if referral_earnings > 0:
            transactions.append({
                'type': 'referral_earnings',
                'amount': referral_earnings,
                'status': 'completed',
                'date': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
            })
        
        # Get withdrawals
        withdrawals = session.query(Withdrawal).filter_by(user_id=user.id).all()
        for w in withdrawals:
            transactions.append({
                'type': 'withdraw',
                'amount': w.amount,
                'status': w.status,
                'date': w.created_at.strftime('%Y-%m-%d %H:%M')
            })
        
        # Sort by date (newest first)
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        return jsonify({'transactions': transactions})
    finally:
        session.close()

@app.route('/api/investments/<int:telegram_id>', methods=['GET'])
def get_investments(telegram_id):
    """Get investment history for a user"""
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
                'amount': inv.amount,
                'status': 'active' if inv.is_active else 'completed',
                'date': inv.start_date.strftime('%Y-%m-%d %H:%M'),
                'field': inv.field_number,
                'paid_out': inv.paid_out,
                'total_return': inv.expected_return
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
        
        return jsonify({
            'success': True,
            'message': f'Successfully invested ${amount} in Field #{field_number}'
        })
    finally:
        session.close()

@app.route('/api/invest_locked', methods=['POST'])
def invest_locked():
    """New endpoint for locked investments with 1, 7, or 30 day options"""
    data = request.json
    telegram_id = data.get('telegram_id')
    field_number = data.get('field_number')
    amount = data.get('amount')
    lock_period = data.get('lock_period', 30)
    
    if not telegram_id or not field_number or not amount or not lock_period:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    # Validate lock period
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
        
        # Calculate return based on lock period (2%, 15%, 65%)
        multipliers = {1: 1.02, 7: 1.15, 30: 1.65}
        multiplier = multipliers.get(lock_period, 1.65)
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
    """Check for a deposit with a specific expected amount - MANUAL CHECK"""
    telegram_id = request.args.get('telegram_id')
    expected_amount = request.args.get('expected_amount', type=float)
    
    if not telegram_id or not expected_amount:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    try:
        # Use the deposit scanner with amount filtering
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            deposit_scanner.check_deposit_with_amount(
                int(telegram_id),
                expected_amount,
                None  # bot will be passed from main when called from scheduler
            )
        )
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=5001)

from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from database.models import User, Withdrawal, Investment, Deposit, DailyPayout
from sqlalchemy import func

app = Flask(__name__)
CORS(app)

db = DatabaseManager()

# Project wallet - blocked from user use
PROJECT_WALLET = '0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76'

@app.route('/api/get_wallet', methods=['GET'])
def get_wallet():
    telegram_id = request.args.get('telegram_id', '0')
    if telegram_id == '0':
        return jsonify({'success': False, 'message': 'Missing telegram_id'})
    
    session = db.get_session()
    user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
    if not user:
        return jsonify({'success': True, 'wallet_address': ''})
    
    return jsonify({'success': True, 'wallet_address': user.wallet_address or ''})

@app.route('/api/save_wallet', methods=['POST'])
def save_wallet():
    data = request.json
    telegram_id = data.get('telegram_id')
    wallet_address = data.get('wallet_address', '')
    
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'})
    
    session = db.get_session()
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
        return jsonify({'success': False, 'message': 'This is the project wallet. Please enter your own wallet address.'})
    
    user.wallet_address = wallet_address
    session.commit()
    
    return jsonify({'success': True, 'message': 'Wallet saved successfully'})

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
        return jsonify({'success': False, 'message': 'Cannot withdraw to project wallet. Please use your own wallet address.'})
    
    session = db.get_session()
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

@app.route('/api/get_referral_code', methods=['GET'])
def get_referral_code():
    telegram_id = request.args.get('telegram_id', '0')
    
    if telegram_id == '0':
        return jsonify({'success': False, 'message': 'User not found'})
    
    session = db.get_session()
    user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
    
    if not user:
        return jsonify({'success': False, 'message': 'User not found'})
    
    return jsonify({
        'success': True,
        'referral_code': user.referral_code
    })

@app.route('/api/referral_stats/<int:telegram_id>', methods=['GET'])
def get_referral_stats(telegram_id):
    """Get referral statistics - single level only"""
    try:
        session = db.get_session()
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found'})
        
        # Level 1 referrals only (no multi-tier)
        level1_refs = session.query(User).filter_by(referred_by=user.id).all()
        level1_count = len(level1_refs)
        level1_earnings = sum(r.referral_deposit_earnings or 0 for r in level1_refs)
        
        return jsonify({
            'success': True,
            'level1_count': level1_count,
            'level1_earnings': level1_earnings,
            'total_referrals': level1_count,
            'total_earnings': level1_earnings
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/user', methods=['GET'])
def get_user():
    telegram_id = request.args.get('telegram_id', '0')
    
    if telegram_id == '0':
        return jsonify({
            'success': True,
            'balance': 0,
            'fields': [],
            'referrals': 0,
            'referral_earned': 0,
            'investment_earnings': 0,
            'total_earnings': 0,
            'level1_count': 0,
            'level2_count': 0
        })
    
    session = db.get_session()
    user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
    
    if not user:
        return jsonify({
            'success': True,
            'balance': 0,
            'fields': [],
            'referrals': 0,
            'referral_earned': 0,
            'investment_earnings': 0,
            'total_earnings': 0,
            'level1_count': 0,
            'level2_count': 0
        })
    
    # Get investments
    investments = session.query(Investment).filter_by(user_id=user.id).all()
    fields = []
    for inv in investments:
        if inv.is_active or not inv.is_completed:
            next_payout = inv.next_payout_date
            fields.append({
                'field_number': inv.field_number,
                'amount': inv.amount,
                'total_return': inv.total_return,
                'paid_out': inv.paid_out,
                'start_date': inv.start_date.isoformat(),
                'is_active': inv.is_active,
                'next_payout_date': next_payout.isoformat() if next_payout else None
            })
    
    # Get referrals (level 1 only for display)
    level1_refs = session.query(User).filter_by(referred_by=user.id).all()
    level1_count = len(level1_refs)
    
    # Get level 2 count (keeping for backward compatibility, but will always be 0)
    level2_count = 0
    
    referral_earned = user.referral_earnings_all_time or 0
    investment_earnings = user.investment_earnings_all_time or 0
    total_earnings = referral_earned + investment_earnings
    
    return jsonify({
        'success': True,
        'balance': user.balance,
        'fields': fields,
        'referrals': level1_count,
        'referral_earned': referral_earned,
        'investment_earnings': investment_earnings,
        'total_earnings': total_earnings,
        'level1_count': level1_count,
        'level2_count': level2_count
    })

@app.route('/api/real_history', methods=['GET'])
def get_real_history():
    telegram_id = request.args.get('telegram_id', '0')
    
    if telegram_id == '0':
        return jsonify({'success': False, 'message': 'User not found'})
    
    session = db.get_session()
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
    
    # Get earnings (daily payouts)
    payouts = session.query(DailyPayout).filter_by(user_id=user.id).all()
    for p in payouts:
        transactions.append({
            'type': 'earnings',
            'amount': p.amount,
            'status': 'completed',
            'date': p.paid_at.strftime('%Y-%m-%d %H:%M')
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

@app.route('/api/invest', methods=['POST'])
def invest():
    data = request.json
    telegram_id = data.get('telegram_id')
    field_number = data.get('field_number')
    amount = data.get('amount')
    
    if not telegram_id or not field_number or not amount:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    session = db.get_session()
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=5001)

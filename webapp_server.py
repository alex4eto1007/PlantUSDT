from flask import Flask, send_from_directory, jsonify, request
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, static_folder='webapp')

from database.db_manager import DatabaseManager
from database.models import User, Investment, Withdrawal

db = DatabaseManager()

PROJECT_WALLET = '0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76'

@app.route('/')
def index():
    return send_from_directory('webapp', 'index.html')

@app.route('/<path:path>')
def serve(path):
    return send_from_directory('webapp', path)

@app.route('/api/user', methods=['GET'])
def get_user():
    telegram_id = request.args.get('telegram_id', '0')
    
    if telegram_id == '0':
        return jsonify({
            'success': True,
            'balance': 0,
            'fields': [],
            'referrals': 0,
            'referral_earned': 0
        })
    
    session = db.get_session()
    user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
    
    if not user:
        return jsonify({
            'success': True,
            'balance': 0,
            'fields': [],
            'referrals': 0,
            'referral_earned': 0
        })
    
    investments = session.query(Investment).filter_by(user_id=user.id).all()
    fields = []
    for inv in investments:
        if inv.is_active or not inv.is_completed:
            fields.append({
                'field_number': inv.field_number,
                'amount': inv.amount,
                'total_return': inv.total_return,
                'paid_out': inv.paid_out,
                'start_date': inv.start_date.isoformat(),
                'is_active': inv.is_active
            })
    
    referrals = session.query(User).filter_by(referred_by=user.id).count()
    
    return jsonify({
        'success': True,
        'balance': user.balance,
        'fields': fields,
        'referrals': referrals,
        'referral_earned': 0
    })

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
    total_return = amount * Config.DAILY_RATE * Config.INVESTMENT_DAYS
    
    investment = Investment(
        user_id=user.id,
        field_number=field_number,
        amount=amount,
        total_return=total_return
    )
    session.add(investment)
    
    user.balance -= amount
    user.total_invested += amount
    
    session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Successfully invested ${amount} in Field #{field_number}'
    })

@app.route('/api/check_deposit', methods=['GET'])
def check_deposit():
    return jsonify({'success': True, 'message': 'Deposit check in progress'})

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    telegram_id = data.get('telegram_id')
    amount = data.get('amount')
    address = data.get('address')
    
    if not telegram_id or not amount or not address:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    if address.lower() == PROJECT_WALLET.lower():
        return jsonify({'success': False, 'message': 'Cannot withdraw to project wallet. Please use your own wallet address.'})
    
    session = db.get_session()
    user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
    
    if not user:
        return jsonify({'success': False, 'message': 'User not found'})
    
    # ============================================
    # CHECK BALANCE
    # ============================================
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
    
    return jsonify({'success': True, 'message': 'Withdrawal request submitted'})

@app.route('/api/history', methods=['GET'])
def get_history():
    telegram_id = request.args.get('telegram_id', '0')
    tx_type = request.args.get('type', 'all')
    
    transactions = [
        {'type': 'deposit', 'amount': 50.00, 'status': 'completed', 'date': '2026-06-17'},
        {'type': 'earnings', 'amount': 2.00, 'status': 'completed', 'date': '2026-06-16'}
    ]
    
    if tx_type != 'all':
        transactions = [tx for tx in transactions if tx['type'] == tx_type]
    
    return jsonify({'transactions': transactions})

@app.route('/api/save_wallet', methods=['POST'])
def save_wallet():
    data = request.json
    telegram_id = data.get('telegram_id')
    wallet_address = data.get('wallet_address', '')
    
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'})
    
    if not wallet_address or wallet_address == '':
        session = db.get_session()
        user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
        if user:
            user.wallet_address = ''
            session.commit()
            return jsonify({'success': True, 'message': 'Wallet disconnected'})
        return jsonify({'success': False, 'message': 'User not found'})
    
    if not wallet_address.startswith('0x') or len(wallet_address) != 42:
        return jsonify({'success': False, 'message': 'Invalid wallet address'})
    
    if wallet_address.lower() == PROJECT_WALLET.lower():
        return jsonify({'success': False, 'message': 'This is the project wallet. Please enter your own wallet address.'})
    
    session = db.get_session()
    user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
    
    if not user:
        return jsonify({'success': False, 'message': 'User not found'})
    
    user.wallet_address = wallet_address
    session.commit()
    
    return jsonify({'success': True, 'message': 'Wallet saved successfully'})

@app.route('/api/get_wallet', methods=['GET'])
def get_wallet():
    telegram_id = request.args.get('telegram_id', '0')
    
    if telegram_id == '0':
        return jsonify({'success': False, 'message': 'User not found'})
    
    session = db.get_session()
    user = session.query(User).filter_by(telegram_id=int(telegram_id)).first()
    
    if not user:
        return jsonify({'success': False, 'message': 'User not found'})
    
    return jsonify({
        'success': True,
        'wallet_address': user.wallet_address or ''
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)

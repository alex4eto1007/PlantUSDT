from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from database.models import User, Withdrawal

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
    
    # ============================================
    # CONVERT AMOUNT TO FLOAT - FIXED
    # ============================================
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
    
    # ============================================
    # CHECK BALANCE
    # ============================================
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=5001)

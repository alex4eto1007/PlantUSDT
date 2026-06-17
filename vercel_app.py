from flask import Flask, send_from_directory, jsonify, request
import os

app = Flask(__name__, static_folder='webapp')

# Project wallet - blocked from user use
PROJECT_WALLET = '0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76'

# In-memory storage for demo (wallets reset on restart)
user_wallets = {}

@app.route('/')
def index():
    return send_from_directory('webapp', 'index.html')

@app.route('/<path:path>')
def serve(path):
    return send_from_directory('webapp', path)

@app.route('/api/get_wallet', methods=['GET'])
def get_wallet():
    telegram_id = request.args.get('telegram_id', '0')
    return jsonify({
        'success': True,
        'wallet_address': user_wallets.get(telegram_id, '')
    })

@app.route('/api/save_wallet', methods=['POST'])
def save_wallet():
    data = request.json
    telegram_id = data.get('telegram_id')
    wallet_address = data.get('wallet_address', '')
    
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'})
    
    # If empty, disconnect
    if not wallet_address:
        user_wallets[telegram_id] = ''
        return jsonify({'success': True, 'message': 'Wallet disconnected'})
    
    # Validate
    if not wallet_address.startswith('0x') or len(wallet_address) != 42:
        return jsonify({'success': False, 'message': 'Invalid wallet address'})
    
    # Block project wallet
    if wallet_address.lower() == PROJECT_WALLET.lower():
        return jsonify({'success': False, 'message': 'This is the project wallet. Please enter your own wallet address.'})
    
    user_wallets[telegram_id] = wallet_address
    return jsonify({'success': True, 'message': 'Wallet saved successfully'})

@app.route('/api/user', methods=['GET'])
def get_user():
    return jsonify({
        'success': True,
        'balance': 0,
        'fields': [],
        'referrals': 0,
        'referral_earned': 0
    })

@app.route('/api/invest', methods=['POST'])
def invest():
    return jsonify({'success': False, 'message': 'Please use the bot for investments'})

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    address = data.get('address', '')
    
    if address.lower() == PROJECT_WALLET.lower():
        return jsonify({'success': False, 'message': 'Cannot withdraw to project wallet'})
    
    return jsonify({'success': True, 'message': 'Withdrawal request submitted'})

@app.route('/api/check_deposit', methods=['GET'])
def check_deposit():
    return jsonify({'success': True, 'message': 'Deposit check in progress'})

@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify({
        'transactions': [
            {'type': 'deposit', 'amount': 50.00, 'status': 'completed', 'date': '2026-06-17'},
            {'type': 'earnings', 'amount': 2.00, 'status': 'completed', 'date': '2026-06-16'}
        ]
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
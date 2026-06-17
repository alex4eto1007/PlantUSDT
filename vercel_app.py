from flask import Flask, send_from_directory, jsonify, request
import os
import json
import urllib.request
import urllib.error

app = Flask(__name__, static_folder='webapp')

VPS_API_URL = "http://167.233.132.127:5001"
PROJECT_WALLET = '0x6b2672E8b8A3D610AD3C148C70627f3b79D5cF76'

@app.route('/')
def index():
    return send_from_directory('webapp', 'index.html')

@app.route('/<path:path>')
def serve(path):
    return send_from_directory('webapp', path)

@app.route('/api/get_wallet', methods=['GET'])
def get_wallet():
    telegram_id = request.args.get('telegram_id', '0')
    
    try:
        url = f"{VPS_API_URL}/api/get_wallet?telegram_id={telegram_id}"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            return jsonify(data)
    except:
        pass
    
    return jsonify({'success': True, 'wallet_address': ''})

@app.route('/api/save_wallet', methods=['POST'])
def save_wallet():
    data = request.json
    telegram_id = data.get('telegram_id')
    wallet_address = data.get('wallet_address', '')
    
    if not telegram_id:
        return jsonify({'success': False, 'message': 'Missing telegram_id'})
    
    try:
        url = f"{VPS_API_URL}/api/save_wallet"
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode())
            return jsonify(result)
    except:
        pass
    
    return jsonify({'success': False, 'message': 'Could not connect to VPS API'})

# ============================================
# FORWARD WITHDRAW TO VPS API
# ============================================
@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    
    try:
        url = f"{VPS_API_URL}/api/withdraw"
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode())
            return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

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

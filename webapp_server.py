from flask import Flask, send_from_directory, jsonify, request
import os
import json
from datetime import datetime

app = Flask(__name__, static_folder='webapp')

@app.route('/')
def serve_index():
    return send_from_directory('webapp', 'index.html')

@app.route('/<path:path>')
def serve_file(path):
    return send_from_directory('webapp', path)

@app.route('/api/user')
def get_user():
    # Sample user data - Replace with actual database later
    return jsonify({
        'success': True,
        'balance': 125.50,
        'total_invested': 100.00,
        'total_earned': 25.50,
        'total_deposited': 100.00,
        'referrals': 3,
        'username': 'User'
    })

@app.route('/api/check_deposit', methods=['GET'])
def check_deposit():
    return jsonify({'success': True, 'message': 'Deposit check in progress'})

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    amount = data.get('amount')
    address = data.get('address')
    return jsonify({'success': True, 'message': 'Withdrawal request submitted'})

@app.route('/api/history', methods=['GET'])
def get_history():
    tx_type = request.args.get('type', 'all')
    transactions = [
        {'type': 'deposit', 'amount': 50.00, 'status': 'completed', 'date': '2026-06-17T10:00:00'},
        {'type': 'earnings', 'amount': 2.00, 'status': 'completed', 'date': '2026-06-16T10:00:00'},
        {'type': 'deposit', 'amount': 50.00, 'status': 'completed', 'date': '2026-06-15T10:00:00'}
    ]
    
    if tx_type != 'all':
        transactions = [tx for tx in transactions if tx['type'] == tx_type]
    
    return jsonify({'transactions': transactions})

@app.route('/api/verify', methods=['POST'])
def verify():
    """Verify user identity from Telegram WebApp"""
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
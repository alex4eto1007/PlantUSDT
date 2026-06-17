from flask import Flask, send_from_directory, jsonify, request
import os
import json

# Create Flask app with webapp folder
app = Flask(__name__, static_folder='webapp')

# Serve HTML pages
@app.route('/')
def index():
    return send_from_directory('webapp', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    """Serve any file from webapp folder"""
    try:
        return send_from_directory('webapp', path)
    except Exception as e:
        print(f"Error serving {path}: {e}")
        return jsonify({'error': 'File not found'}), 404

# API Routes
@app.route('/api/user')
def get_user():
    """Get user data - sample data for now"""
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
    return jsonify({'success': True, 'message': 'Checking deposits...'})

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    data = request.get_json() or {}
    return jsonify({
        'success': True,
        'message': 'Withdrawal request submitted',
        'amount': data.get('amount', 0)
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    tx_type = request.args.get('type', 'all')
    transactions = [
        {'type': 'deposit', 'amount': 50.00, 'status': 'completed', 'date': '2026-06-17'},
        {'type': 'earnings', 'amount': 2.00, 'status': 'completed', 'date': '2026-06-16'},
        {'type': 'deposit', 'amount': 30.00, 'status': 'completed', 'date': '2026-06-15'}
    ]
    if tx_type != 'all':
        transactions = [tx for tx in transactions if tx['type'] == tx_type]
    return jsonify({'transactions': transactions})

@app.route('/api/verify', methods=['POST'])
def verify():
    """Verify Telegram WebApp user data"""
    return jsonify({'success': True})

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# For local development
if __name__ == '__main__':
    app.run(debug=True, port=5000)
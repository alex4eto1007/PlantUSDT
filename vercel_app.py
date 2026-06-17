from flask import Flask, send_from_directory, jsonify

app = Flask(__name__, static_folder='webapp')

@app.route('/')
def index():
    return send_from_directory('webapp', 'index.html')

@app.route('/<path:path>')
def serve(path):
    return send_from_directory('webapp', path)

@app.route('/api/user')
def user():
    return jsonify({
        'success': True,
        'balance': 125.50,
        'total_invested': 100.00,
        'total_earned': 25.50,
        'total_deposited': 100.00,
        'referrals': 3
    })

@app.route('/api/check_deposit')
def check_deposit():
    return jsonify({'success': True})

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    return jsonify({'success': True})

@app.route('/api/history')
def history():
    return jsonify({
        'transactions': [
            {'type': 'deposit', 'amount': 50, 'status': 'completed', 'date': '2026-06-17'},
            {'type': 'earnings', 'amount': 2, 'status': 'completed', 'date': '2026-06-16'}
        ]
    })

if __name__ == '__main__':
    app.run()
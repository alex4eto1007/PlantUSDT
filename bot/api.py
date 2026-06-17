from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DatabaseManager
from database.models import User

app = Flask(__name__)
CORS(app)  # Allow all origins

db = DatabaseManager()

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
    
    user.wallet_address = wallet_address
    session.commit()
    
    return jsonify({'success': True, 'message': 'Wallet saved successfully'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=5001)

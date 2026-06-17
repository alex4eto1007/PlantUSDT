from database.db_manager import DatabaseManager
from database.models import User

db = DatabaseManager()
session = db.get_session()

user = session.query(User).filter_by(telegram_id=6988485148).first()

if user:
    user.is_admin = True
    session.commit()
    print(f'✅ Admin set successfully for @{user.username}!')
else:
    print('❌ User not found. Send /start to the bot first.')
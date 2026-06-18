from database.db_manager import DatabaseManager
from database.models import User
import uuid

db = DatabaseManager()
session = db.get_session()

users = session.query(User).all()

print("🔄 Regenerating referral codes...")

for user in users:
    while True:
        new_code = str(uuid.uuid4())[:8]
        existing = session.query(User).filter_by(referral_code=new_code).first()
        if not existing or existing.id == user.id:
            break
    
    old_code = user.referral_code
    user.referral_code = new_code
    print(f"✅ {user.username}: {old_code} → {new_code}")

session.commit()
print("\n🎉 All referral codes updated successfully!")

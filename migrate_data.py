#!/usr/bin/env python
import sqlite3
from database.db_manager import DatabaseManager
from database.models import User, Investment, Deposit, DailyPayout, Withdrawal
import os

# Check if SQLite database exists
if not os.path.exists('plantusdt.db'):
    print("❌ SQLite database 'plantusdt.db' not found!")
    print("   If you have no data to migrate, you can skip this step.")
    exit(1)

# SQLite connection
sqlite_conn = sqlite3.connect('plantusdt.db')
sqlite_cursor = sqlite_conn.cursor()

# PostgreSQL session
db = DatabaseManager()
session = db.get_session()

print("🔄 Starting migration from SQLite to PostgreSQL...")
print()

# Migrate Users
print("📦 Migrating Users...")
try:
    users = sqlite_cursor.execute("SELECT * FROM users").fetchall()
    for row in users:
        user = User(
            id=row[0],
            telegram_id=int(row[1]),
            username=row[2],
            first_name=row[3],
            wallet_address=row[4],
            balance=float(row[5]) if row[5] is not None else 0.0,
            total_invested=float(row[6]) if row[6] is not None else 0.0,
            total_earned=float(row[7]) if row[7] is not None else 0.0,
            total_deposited=float(row[8]) if row[8] is not None else 0.0,
            total_earnings_all_time=float(row[9]) if row[9] is not None else 0.0,
            investment_earnings_all_time=float(row[10]) if row[10] is not None else 0.0,
            referral_earnings_all_time=float(row[11]) if row[11] is not None else 0.0,
            referred_by=int(row[12]) if row[12] is not None else None,
            referral_code=row[13],  # Keep as string!
            referral_earnings=float(row[14]) if row[14] is not None else 0.0,
            can_be_referred=bool(row[15]) if row[15] is not None else True,
            referred_at=row[16],
            is_active=bool(row[17]) if row[17] is not None else True,
            is_admin=bool(row[18]) if row[18] is not None else False,
            created_at=row[19],
            last_deposit_check=row[20]
        )
        session.add(user)
    session.commit()
    print(f"   ✅ {len(users)} users migrated")
except Exception as e:
    print(f"   ❌ Error migrating users: {e}")
    session.rollback()

# Migrate Investments
print("📦 Migrating Investments...")
try:
    investments = sqlite_cursor.execute("SELECT * FROM investments").fetchall()
    for row in investments:
        inv = Investment(
            id=row[0],
            user_id=int(row[1]),
            field_number=int(row[2]),
            amount=float(row[3]) if row[3] is not None else 0.0,
            daily_rate=float(row[4]) if row[4] is not None else 0.02,
            total_return=float(row[5]) if row[5] is not None else 0.0,
            paid_out=float(row[6]) if row[6] is not None else 0.0,
            referral_earnings_paid=float(row[7]) if row[7] is not None else 0.0,
            start_date=row[8],
            end_date=row[9],
            last_payout_date=row[10],
            next_payout_date=row[11],
            is_active=bool(row[12]) if row[12] is not None else True,
            is_completed=bool(row[13]) if row[13] is not None else False,
            principal_returned=bool(row[14]) if row[14] is not None else False
        )
        session.add(inv)
    session.commit()
    print(f"   ✅ {len(investments)} investments migrated")
except Exception as e:
    print(f"   ❌ Error migrating investments: {e}")
    session.rollback()

# Migrate Deposits
print("📦 Migrating Deposits...")
try:
    deposits = sqlite_cursor.execute("SELECT * FROM deposits").fetchall()
    for row in deposits:
        dep = Deposit(
            id=row[0],
            user_id=int(row[1]),
            amount=float(row[2]) if row[2] is not None else 0.0,
            tx_hash=row[3],
            from_address=row[4],
            block_number=int(row[5]) if row[5] is not None else 0,
            confirmed_at=row[6],
            processed=bool(row[7]) if row[7] is not None else False
        )
        session.add(dep)
    session.commit()
    print(f"   ✅ {len(deposits)} deposits migrated")
except Exception as e:
    print(f"   ❌ Error migrating deposits: {e}")
    session.rollback()

# Migrate DailyPayouts
print("📦 Migrating DailyPayouts...")
try:
    payouts = sqlite_cursor.execute("SELECT * FROM daily_payouts").fetchall()
    for row in payouts:
        payout = DailyPayout(
            id=row[0],
            user_id=int(row[1]),
            investment_id=int(row[2]),
            amount=float(row[3]) if row[3] is not None else 0.0,
            day_number=int(row[4]) if row[4] is not None else 0,
            paid_at=row[5]
        )
        session.add(payout)
    session.commit()
    print(f"   ✅ {len(payouts)} payouts migrated")
except Exception as e:
    print(f"   ❌ Error migrating payouts: {e}")
    session.rollback()

# Migrate Withdrawals
print("📦 Migrating Withdrawals...")
try:
    withdrawals = sqlite_cursor.execute("SELECT * FROM withdrawals").fetchall()
    for row in withdrawals:
        w = Withdrawal(
            id=row[0],
            user_id=int(row[1]),
            amount=float(row[2]) if row[2] is not None else 0.0,
            fee=float(row[3]) if row[3] is not None else 0.0,
            net_amount=float(row[4]) if row[4] is not None else 0.0,
            wallet_address=row[5],
            status=row[6] if row[6] is not None else 'pending',
            tx_hash=row[7],
            created_at=row[8],
            processed_at=row[9]
        )
        session.add(w)
    session.commit()
    print(f"   ✅ {len(withdrawals)} withdrawals migrated")
except Exception as e:
    print(f"   ❌ Error migrating withdrawals: {e}")
    session.rollback()

# Close connections
sqlite_conn.close()
session.close()

print()
print("✅ Migration complete!")

# Show summary
print()
print("📊 Migration Summary:")
print(f"   Users: {len(users) if 'users' in locals() else 0}")
print(f"   Investments: {len(investments) if 'investments' in locals() else 0}")
print(f"   Deposits: {len(deposits) if 'deposits' in locals() else 0}")
print(f"   Payouts: {len(payouts) if 'payouts' in locals() else 0}")
print(f"   Withdrawals: {len(withdrawals) if 'withdrawals' in locals() else 0}")

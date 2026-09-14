#!/usr/bin/env python3
"""
Manual Credit Script for PlantUSDT

Usage:
  python manual_credit.py <user_id> <amount> <type> [tx_hash] [description]

Types:
  - reward:       Bonus/giveaway (balance only)
  - compensation: Goodwill compensation (balance only)
  - deposit:      Missed deposit (balance + total_deposited + audit record)

Examples:
  python manual_credit.py 7736953092 0.50 reward "Bug bounty reward"
  python manual_credit.py 7736953092 0.10 compensation "Sorry for the delay"
  python manual_credit.py 7736953092 5.00 deposit 0xea6b284c... "Missed deposit from Binance"
"""

import sys
import os
from datetime import datetime, timezone
from decimal import Decimal

sys.path.insert(0, '/root/PlantUSDT')

from config.settings import Config
from database.db_manager import DatabaseManager
from database.models import User, AuditLog, Deposit

db = DatabaseManager()


def print_usage():
    print("""
Manual Credit Script

Usage:
  python manual_credit.py <user_id> <amount> <type> [tx_hash] [description]

Types:
  - reward:       Bonus/giveaway (balance only)
  - compensation: Goodwill compensation (balance only)
  - deposit:      Missed deposit (balance + total_deposited + audit record)

Examples:
  python manual_credit.py 7736953092 0.50 reward "Bug bounty reward"
  python manual_credit.py 7736953092 0.10 compensation "Sorry for the delay"
  python manual_credit.py 7736953092 5.00 deposit 0xea6b284c... "Missed deposit"
""")


def main():
    if len(sys.argv) < 4:
        print_usage()
        sys.exit(1)

    session = None
    try:
        user_id = int(sys.argv[1])
        amount = Decimal(str(sys.argv[2]))
        credit_type = sys.argv[3].lower()
        tx_hash = sys.argv[4] if len(sys.argv) > 4 else None
        description = ' '.join(sys.argv[5:]) if len(sys.argv) > 5 else ''

        if credit_type not in ['reward', 'compensation', 'deposit']:
            print(f"❌ Invalid type: {credit_type}")
            print("Available types: reward, compensation, deposit")
            sys.exit(1)

        session = db.get_session()
        user = session.query(User).filter_by(telegram_id=user_id).first()

        if not user:
            print(f"❌ User {user_id} not found")
            session.close()
            sys.exit(1)

        old_balance = Decimal(user.balance or 0)
        new_balance = old_balance + amount

        print(f"\n📊 User: @{user.username or 'User'} ({user_id})")
        print(f"💰 Amount: ${amount:.2f}")
        print(f"📝 Type: {credit_type}")
        print(f"📊 Old balance: ${old_balance:.2f}")
        print(f"📊 New balance: ${new_balance:.2f}")

        if credit_type == "deposit":
            print(f"🔗 TX Hash: {tx_hash or 'Manual'}")
            print(f"📝 Description: {description or 'Missed deposit'}")

        print("\n⚠️ Confirm? (yes/no): ", end="")
        confirm = input().strip().lower()

        if confirm != 'yes':
            print("❌ Cancelled")
            session.close()
            sys.exit(0)

        # Update balance
        user.balance = new_balance

        # Log to audit log
        audit = AuditLog(
            user_id=user.id,
            action=f'manual_credit_{credit_type}',
            field_changed='balance',
            old_value=float(old_balance),
            new_value=float(new_balance),
            amount=float(amount),
            description=f"{credit_type}: {description}" if description else credit_type,
            source='admin',
            created_by=0,
            created_at=datetime.now(timezone.utc)
        )
        session.add(audit)

        if credit_type == "deposit":
            # Update total_deposited only — no investment, no total_invested change
            user.total_deposited = (user.total_deposited or Decimal('0')) + amount

            # Create deposit record (so history shows it)
            deposit = Deposit(
                user_id=user.id,
                amount=float(amount),
                tx_hash=tx_hash or f'manual_{int(datetime.now(timezone.utc).timestamp())}',
                from_address='manual_credit',
                block_number=0,
                confirmed_at=datetime.now(timezone.utc),
                processed=True,
                network='polygon'
            )
            session.add(deposit)
            session.commit()

            print(f"\n✅ Deposit processed successfully!")
            print(f"📊 New balance: ${new_balance:.2f}")
            print(f"📊 Total deposited: ${user.total_deposited:.2f}")
            print(f"📊 Total invested (unchanged): ${user.total_invested or 0:.2f}")

        else:
            # Reward or compensation — balance only
            session.commit()
            print(f"\n✅ {credit_type.capitalize()} credited successfully!")
            print(f"📊 New balance: ${new_balance:.2f}")

    except ValueError as e:
        print(f"❌ Invalid input: {e}")
        print_usage()
        if session:
            session.rollback()
            session.close()
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        if session:
            try:
                session.rollback()
                session.close()
            except Exception:
                pass
        sys.exit(1)
    finally:
        if session:
            try:
                session.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()

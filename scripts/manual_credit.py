#!/usr/bin/env python3
"""
Manual Credit Script for PlantUSDT

Usage:
  python manual_credit.py <user_id> <amount> <type> [tx_hash] [description]

Types:
  - reward: Bonus/giveaway (balance only)
  - compensation: Goodwill compensation (balance only)  
  - deposit: Missed deposit (full deposit flow)

Examples:
  python manual_credit.py 7736953092 0.50 reward "Bug bounty reward"
  python manual_credit.py 7736953092 0.10 compensation "Sorry for the delay"
  python manual_credit.py 7736953092 5.00 deposit 0xea6b284c... "Missed deposit from Binance"
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/root/PlantUSDT')

from config.settings import Config
from database.db_manager import DatabaseManager
from database.models import User, AuditLog, Investment, Deposit, UserTaskProgress
from services.task_system import check_task_conditions

db = DatabaseManager()

def print_usage():
    print("""
Manual Credit Script

Usage:
  python manual_credit.py <user_id> <amount> <type> [tx_hash] [description]

Types:
  - reward: Bonus/giveaway (balance only)
  - compensation: Goodwill compensation (balance only)
  - deposit: Missed deposit (full deposit flow)

Examples:
  python manual_credit.py 7736953092 0.50 reward "Bug bounty reward"
  python manual_credit.py 7736953092 0.10 compensation "Sorry for the delay"
  python manual_credit.py 7736953092 5.00 deposit 0xea6b284c... "Missed deposit"
""")

def main():
    if len(sys.argv) < 4:
        print_usage()
        sys.exit(1)

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
            created_at=datetime.now(timezone.UTC)
        )
        session.add(audit)

        if credit_type == "deposit":
            # Update total_deposited
            user.total_deposited = (user.total_deposited or Decimal('0')) + amount

            # Create deposit record
            deposit = Deposit(
                user_id=user.id,
                amount=float(amount),
                tx_hash=tx_hash or f'manual_{int(datetime.now(timezone.UTC).timestamp())}',
                from_address='manual_credit',
                block_number=0,
                confirmed_at=datetime.now(timezone.UTC),
                processed=True,
                network='polygon'
            )
            session.add(deposit)

            # If amount >= $5, create investment
            if amount >= 5:
                user.total_invested = (user.total_invested or Decimal('0')) + amount

                now = datetime.now(timezone.UTC)
                unlock_date = now + timedelta(days=30)

                investment = Investment(
                    user_id=user.id,
                    field_number=1,
                    amount=float(amount),
                    lock_period=30,
                    unlock_date=unlock_date,
                    expected_return=float(amount * 1.80),
                    start_date=now,
                    end_date=unlock_date,
                    is_active=True,
                    is_locked=True,
                    completed_at=None,
                    principal_returned=False
                )
                session.add(investment)
                print(f"✅ Investment created: ${amount:.2f} locked for 30 days")

            # Initialize missing tasks
            task_ids = [1, 2, 3, 4, 5, 6, 7, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44]
            created_count = 0
            for task_id in task_ids:
                existing = session.query(UserTaskProgress).filter_by(
                    user_id=user.id,
                    task_id=task_id
                ).first()
                if not existing:
                    task = UserTaskProgress(
                        user_id=user.id,
                        task_id=task_id,
                        completed=False,
                        claimed=False
                    )
                    session.add(task)
                    created_count += 1

            if created_count > 0:
                print(f"✅ {created_count} tasks initialized")

            session.commit()

            # Trigger task system
            print("🔄 Checking tasks...")
            check_task_conditions(user, session)
            print("✅ Tasks checked")

            print(f"\n✅ Deposit processed successfully!")
            print(f"📊 New balance: ${new_balance:.2f}")
            print(f"📊 Total invested: ${user.total_invested:.2f}")
            print(f"📊 Total deposited: ${user.total_deposited:.2f}")

        else:
            # Reward or compensation — just balance
            session.commit()
            print(f"\n✅ {credit_type.capitalize()} credited successfully!")
            print(f"📊 New balance: ${new_balance:.2f}")

        session.close()

    except ValueError as e:
        print(f"❌ Invalid input: {e}")
        print_usage()
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Pick random winners from the most recent giveaway cycle.
Usage: python scripts/pick_giveaway_winners.py [count=10]
"""

import sys
import os
import random
from datetime import datetime

sys.path.insert(0, '/root/PlantUSDT')
from database.db_manager import DatabaseManager
from database.models import GiveawayEntry

db = DatabaseManager()


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    session = db.get_session()
    try:
        latest = session.query(GiveawayEntry).order_by(GiveawayEntry.created_at.desc()).first()
        if not latest:
            print("❌ No giveaway entries found.")
            return

        cycle_start = latest.cycle_start
        cycle_end = latest.cycle_end

        entries = session.query(GiveawayEntry).filter_by(
            cycle_start=cycle_start,
            cycle_end=cycle_end
        ).all()

        if not entries:
            print("❌ No entries for this cycle.")
            return

        print(f"📊 Cycle: {cycle_start} → {cycle_end}")
        print(f"👥 Eligible users: {len(entries)}")

        winners = random.sample(entries, min(count, len(entries)))

        print("\n🏆 WINNERS:")
        print("=" * 50)
        for i, w in enumerate(winners, 1):
            print(f"{i}. @{w.username or 'User'} ({w.telegram_id}) — {w.ads_watched} ads")

        print("\n📌 Credit them with:")
        print("   python scripts/manual_credit.py <telegram_id> <amount> reward 'Giveaway winner'")
    finally:
        session.close()


if __name__ == "__main__":
    main()

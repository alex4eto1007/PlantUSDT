#!/usr/bin/env python3
"""
Pick random giveaway winners from the most recent cycle, rank them by ads watched,
and calculate their prizes based on a tiered distribution.

Usage:
    python scripts/pick_giveaway_winners.py

Flow:
    1. Load the latest cycle from giveaway_entries
    2. Get all qualified users in that cycle
    3. Randomly pick up to 10 winners
    4. Rank winners by ads_watched (descending)
    5. Prompt admin to enter the prize pool in USDT
    6. Calculate each winner's prize by tier %
    7. Print table + one manual_credit.py line per user
"""

import sys
import os
import random
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, '/root/PlantUSDT')
from database.db_manager import DatabaseManager
from database.models import GiveawayEntry

db = DatabaseManager()

# Tier percentages for 10 winners (sum = 100)
TIER_PERCENTAGES_10 = [20, 15, 12, 10, 9, 8, 7, 7, 6, 6]

MAX_WINNERS = 10


def redistribute_for_fewer(n):
    """
    If fewer than 10 qualified, use the top N tiers and redistribute
    the remaining percentage proportionally upward.
    Always sums to 100.
    """
    if n >= 10:
        return TIER_PERCENTAGES_10[:n]

    top_tiers = TIER_PERCENTAGES_10[:n]
    total_top = sum(top_tiers)
    missing = 100 - total_top

    # Redistribute `missing` proportionally to each tier's weight
    redistributed = []
    running_total = 0
    for i, t in enumerate(top_tiers):
        share = Decimal(missing) * Decimal(t) / Decimal(total_top)
        # Round down to whole percent for all but the last, ensure sum = 100
        if i == n - 1:
            final = 100 - running_total
        else:
            final = int(share.to_integral_value(rounding=ROUND_HALF_UP))
            running_total += final
        if i == n - 1:
            redistributed.append(final)
        else:
            redistributed.append(final)

    # Safety: force sum to exactly 100
    diff = 100 - sum(redistributed)
    if diff != 0:
        redistributed[0] += diff

    return redistributed


def main():
    session = db.get_session()
    try:
        # Step 1 — latest cycle
        latest = session.query(GiveawayEntry).order_by(GiveawayEntry.created_at.desc()).first()
        if not latest:
            print("❌ No giveaway entries found.")
            return

        cycle_start = latest.cycle_start
        cycle_end = latest.cycle_end

        # Step 2 — all qualified users in that cycle
        entries = session.query(GiveawayEntry).filter_by(
            cycle_start=cycle_start,
            cycle_end=cycle_end
        ).all()

        if not entries:
            print("❌ No entries for this cycle.")
            return

        print(f"📊 Cycle: {cycle_start} → {cycle_end}")
        print(f"👥 Qualified users: {len(entries)}")
        print()

        # Step 3 — randomly pick up to MAX_WINNERS
        winner_count = min(MAX_WINNERS, len(entries))
        winners = random.sample(entries, winner_count)
        print(f"🎲 Randomly picked: {winner_count} winners")

        # Step 4 — rank picked winners by ads_watched (descending)
        winners.sort(key=lambda w: w.ads_watched, reverse=True)

        # Step 5 — ask admin for the pool amount
        while True:
            try:
                pool_input = input("\n💰 Enter prize pool (USDT): ").strip()
                pool = Decimal(pool_input)
                if pool <= 0:
                    print("❌ Pool must be greater than 0. Try again.")
                    continue
                break
            except Exception:
                print("❌ Invalid input. Enter a number like 10.00")

        # Step 6 — calculate tier percentages for this winner count
        tiers = redistribute_for_fewer(winner_count)

        # Step 7 — calculate each prize
        print()
        print("🏆 WINNERS (ranked by ads watched):")
        print("━" * 65)

        medals = ["🥇", "🥈", "🥉"]
        credit_lines = []
        total_paid = Decimal('0')

        for i, w in enumerate(winners):
            rank = i + 1
            pct = tiers[i]
            prize = (pool * Decimal(pct) / Decimal(100)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            total_paid += prize

            medal = medals[i] if i < 3 else "  "
            rank_str = f"#{rank:<2}"
            username = w.username or "User"
            handle = f"@{username}"
            tg_id = w.telegram_id

            # Column-aligned print
            print(f"{medal} {rank_str} {handle:<20} ({tg_id})  {w.ads_watched:>4} ads  →  ${prize:.2f} ({pct}%)")

            # Build credit line
            credit_lines.append(
                f"   python scripts/manual_credit.py {tg_id} {prize} reward 'Giveaway #{rank} winner'"
            )

        print("━" * 65)
        print(f"💰 Total: ${total_paid:.2f}")
        print()

        # Step 8 — print credit lines
        print("📌 Credit each winner (copy-paste below):")
        for line in credit_lines:
            print(line)
        print()
        print("📋 Done. Review the amounts before crediting.")

    except KeyboardInterrupt:
        print("\n❌ Cancelled.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()

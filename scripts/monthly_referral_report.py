#!/usr/bin/env python3
"""
Monthly Referral Report — PlantUSDT

Purpose:
  Report users eligible for:
    - $0.30 monthly bonus (100+ valid referrals, 50%+ engaged)
    - No-fee withdrawals (150+ valid referrals, 50%+ engaged)

  This script is READ-ONLY. It does not credit or modify any data.
  You handle rewards manually.

Run:
  python scripts/monthly_referral_report.py

Definitions:
  - Valid referral     = invited user with wallet connected AND total_ads_watched >= 3
  - Engaged referral   = valid referral who, in the last 30 days, did ANY of:
        * Watched >= 2 ads (from ad_logs)
        * Completed >= 1 task (from user_task_progress)
        * Invited >= 1 own referral (from users.created_at)
        * Opened the app (users.last_seen_at within 30 days)
  - Referrer qualifies if:
        * not flagged, not banned
        * >= 100 valid (bonus) OR >= 150 valid (no-fee)
        * >= 50% of valid referrals are engaged
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

sys.path.insert(0, '/root/PlantUSDT')

from database.db_manager import DatabaseManager
from database.models import User, AdLog, UserTaskProgress

db = DatabaseManager()


def main():
    session = db.get_session()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(days=30)

        print("=" * 70)
        print(f"📅 MONTHLY REFERRAL REPORT — {now.strftime('%Y-%m-%d %H:%M UTC')}")
        print("=" * 70)
        print()

        candidate_ids = set()
        all_referrals = session.query(User).filter(User.referred_by.isnot(None)).all()
        referrer_id_counts = {}
        for r in all_referrals:
            referrer_id_counts[r.referred_by] = referrer_id_counts.get(r.referred_by, 0) + 1
        for rid, count in referrer_id_counts.items():
            if count >= 100:
                candidate_ids.add(rid)

        bonus_eligible = []
        no_fee_eligible = []
        skipped_50 = []
        skipped_flagged = []

        for referrer_id in candidate_ids:
            referrer = session.query(User).filter_by(id=referrer_id).first()
            if not referrer:
                continue

            referrals = session.query(User).filter_by(referred_by=referrer_id).all()

            valid_count = 0
            engaged_count = 0

            for ref in referrals:
                if not (ref.wallet_address and ref.wallet_address.strip()):
                    continue
                if (ref.total_ads_watched or 0) < 3:
                    continue

                valid_count += 1

                engaged = False

                if not engaged:
                    ads_30d = session.query(AdLog).filter(
                        AdLog.user_id == ref.id,
                        AdLog.watched_at >= cutoff
                    ).count()
                    if ads_30d >= 2:
                        engaged = True

                if not engaged:
                    tasks_30d = session.query(UserTaskProgress).filter(
                        UserTaskProgress.user_id == ref.id,
                        UserTaskProgress.completed == True,
                        UserTaskProgress.completed_at >= cutoff
                    ).count()
                    if tasks_30d >= 1:
                        engaged = True

                if not engaged:
                    own_refs_30d = session.query(User).filter(
                        User.referred_by == ref.id,
                        User.created_at >= cutoff
                    ).count()
                    if own_refs_30d >= 1:
                        engaged = True

                if not engaged:
                    if ref.last_seen_at and ref.last_seen_at >= cutoff:
                        engaged = True

                if engaged:
                    engaged_count += 1

            if valid_count == 0:
                continue

            pct = (engaged_count / valid_count) * 100

            entry = {
                'referrer': referrer,
                'valid': valid_count,
                'engaged': engaged_count,
                'pct': pct,
            }

            if referrer.flagged_for_anomaly or referrer.is_banned:
                skipped_flagged.append(entry)
                continue

            if pct < 50:
                skipped_50.append(entry)
                continue

            if valid_count >= 150:
                no_fee_eligible.append(entry)
            elif valid_count >= 100:
                bonus_eligible.append(entry)

        bonus_eligible.sort(key=lambda x: x['valid'], reverse=True)
        no_fee_eligible.sort(key=lambda x: x['valid'], reverse=True)
        skipped_50.sort(key=lambda x: x['valid'], reverse=True)
        skipped_flagged.sort(key=lambda x: x['valid'], reverse=True)

        print(f"💰 BONUS ELIGIBLE ($0.30) — 100+ valid & 50%+ engaged ({len(bonus_eligible)}):")
        if not bonus_eligible:
            print("   (none)")
        else:
            for i, e in enumerate(bonus_eligible, 1):
                u = e['referrer']
                print(f"  {i}. @{u.username or u.first_name or 'User'} ({u.telegram_id})  "
                      f"→ {e['valid']} valid | {e['engaged']} engaged ({e['pct']:.0f}%)")
        print()

        print(f"🏦 NO-FEE WITHDRAWAL ELIGIBLE — 150+ valid & 50%+ engaged ({len(no_fee_eligible)}):")
        if not no_fee_eligible:
            print("   (none)")
        else:
            for i, e in enumerate(no_fee_eligible, 1):
                u = e['referrer']
                print(f"  {i}. @{u.username or u.first_name or 'User'} ({u.telegram_id})  "
                      f"→ {e['valid']} valid | {e['engaged']} engaged ({e['pct']:.0f}%)")
        print()

        print(f"⚠️  SKIPPED — under 50% engaged ({len(skipped_50)}):")
        if not skipped_50:
            print("   (none)")
        else:
            for i, e in enumerate(skipped_50, 1):
                u = e['referrer']
                print(f"  {i}. @{u.username or u.first_name or 'User'} ({u.telegram_id})  "
                      f"→ {e['valid']} valid | {e['engaged']} engaged ({e['pct']:.0f}%)")
        print()

        print(f"🚩 SKIPPED — flagged/banned ({len(skipped_flagged)}):")
        if not skipped_flagged:
            print("   (none)")
        else:
            for i, e in enumerate(skipped_flagged, 1):
                u = e['referrer']
                print(f"  {i}. @{u.username or u.first_name or 'User'} ({u.telegram_id})  "
                      f"→ {e['valid']} valid | {e['engaged']} engaged ({e['pct']:.0f}%)")
        print()

        print("=" * 70)
        print(f"📊 TOTALS:")
        print(f"   Bonus eligible:     {len(bonus_eligible)}")
        print(f"   No-fee eligible:    {len(no_fee_eligible)}")
        print(f"   Skipped (<50%):     {len(skipped_50)}")
        print(f"   Skipped (flagged):  {len(skipped_flagged)}")
        print("=" * 70)
        print()

        print()
        print("──────── 📲 TELEGRAM-FORMATTED VERSION (copy/paste) ────────")
        print()

        print(f"📅 *Monthly Referral Report* — {now.strftime('%d %b %Y')}")
        print()

        print(f"💰 *BONUS ELIGIBLE ($0.30)* — {len(bonus_eligible)} users")
        if not bonus_eligible:
            print("_none_")
        else:
            for e in bonus_eligible:
                u = e['referrer']
                uname = f"@{u.username}" if u.username else (u.first_name or "User")
                print(f"• {uname} (`{u.telegram_id}`) — {e['valid']} valid | {e['engaged']} engaged")
        print()

        print(f"🏦 *NO-FEE WITHDRAWAL ELIGIBLE* — {len(no_fee_eligible)} users")
        if not no_fee_eligible:
            print("_none_")
        else:
            for e in no_fee_eligible:
                u = e['referrer']
                uname = f"@{u.username}" if u.username else (u.first_name or "User")
                print(f"• {uname} (`{u.telegram_id}`) — {e['valid']} valid | {e['engaged']} engaged")
        print()

        if skipped_50:
            print(f"⚠️ *SKIPPED — under 50% engaged* ({len(skipped_50)})")
            for e in skipped_50:
                u = e['referrer']
                uname = f"@{u.username}" if u.username else (u.first_name or "User")
                print(f"• {uname} (`{u.telegram_id}`) — {e['valid']} valid | {e['pct']:.0f}%")
            print()

        if skipped_flagged:
            print(f"🚩 *SKIPPED — flagged/banned* ({len(skipped_flagged)})")
            for e in skipped_flagged:
                u = e['referrer']
                uname = f"@{u.username}" if u.username else (u.first_name or "User")
                print(f"• {uname} (`{u.telegram_id}`) — {e['valid']} valid")
            print()

        print(f"📊 Bonus: {len(bonus_eligible)} | No-fee: {len(no_fee_eligible)} | Skipped: {len(skipped_50) + len(skipped_flagged)}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Fix Missing Referral Rewards Script

This script checks for referrals that have met the conditions:
1. Referred user has connected wallet
2. Referred user has watched at least 3 ads
3. Reward hasn't been credited yet

Then adds $0.005 to the referrer's pending_referral_rewards balance and logs it.
"""

import sys
import os
from datetime import datetime, timezone
from decimal import Decimal

sys.path.insert(0, '/root/PlantUSDT')

from database.db_manager import DatabaseManager
from database.models import User, AuditLog

db = DatabaseManager()

def fix_missing_referral_rewards():
    """Check and fix missing referral rewards"""
    session = db.get_session()
    
    try:
        print("🔍 Checking for missing referral rewards...")
        
        eligible_referrals = session.query(User).filter(
            User.referred_by.isnot(None),
            User.wallet_address.isnot(None),
            User.wallet_address != '',
            User.total_ads_watched >= 3
        ).all()
        
        print(f"📊 Found {len(eligible_referrals)} referrals that meet the conditions")
        
        credited_count = 0
        skipped_count = 0
        
        for referred_user in eligible_referrals:
            referrer = session.query(User).filter_by(id=referred_user.referred_by).first()
            
            if not referrer:
                print(f"⚠️ Referrer not found for user {referred_user.telegram_id}")
                skipped_count += 1
                continue
            
            existing = session.query(AuditLog).filter(
                AuditLog.user_id == referrer.id,
                AuditLog.action == 'referral_reward',
                AuditLog.description.like(f'%{referred_user.telegram_id}%')
            ).first()
            
            if existing:
                print(f"⏭️ Reward already given for {referred_user.telegram_id} -> {referrer.telegram_id}")
                skipped_count += 1
                continue
            
            reward = Decimal('0.005')
            old_pending = Decimal(referrer.pending_referral_rewards or 0)
            
            referrer.pending_referral_rewards = old_pending + reward
            
            audit = AuditLog(
                user_id=referrer.id,
                action='referral_reward',
                field_changed='pending_referral_rewards',
                old_value=float(old_pending),
                new_value=float(referrer.pending_referral_rewards),
                amount=float(reward),
                description=f'Referral reward for {referred_user.telegram_id} (wallet + 3 ads) - AUTO',
                source='referral_reward_scheduler',
                created_at=datetime.now(timezone.utc)
            )
            session.add(audit)
            
            credited_count += 1
            print(f"✅ Added $0.005 to pending for {referrer.telegram_id} from referral {referred_user.telegram_id}")
        
        session.commit()
        
        print("\n" + "="*50)
        print(f"✅ Total credited: {credited_count}")
        print(f"⏭️ Total skipped: {skipped_count}")
        print("="*50)
        
        return credited_count
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        return 0
    finally:
        session.close()

if __name__ == "__main__":
    fix_missing_referral_rewards()

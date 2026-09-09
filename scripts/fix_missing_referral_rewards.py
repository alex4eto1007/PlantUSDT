#!/usr/bin/env python3
"""
Fix Missing Referral Rewards Script

This script checks for referrals that have met the conditions:
1. Referred user has connected wallet
2. Referred user has watched at least 3 ads
3. Reward hasn't been credited yet

Then credits $0.002 to the referrer and logs it.
"""

import sys
import os
from datetime import datetime
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/root/PlantUSDT')

from database.db_manager import DatabaseManager
from database.models import User, AuditLog

db = DatabaseManager()

def fix_missing_referral_rewards():
    """Check and fix missing referral rewards"""
    session = db.get_session()
    
    try:
        print("🔍 Checking for missing referral rewards...")
        
        # Find all users who:
        # 1. Have a referrer
        # 2. Have a connected wallet
        # 3. Have watched at least 3 ads
        # 4. Haven't been rewarded yet
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
            
            # Check if reward was already given
            existing = session.query(AuditLog).filter(
                AuditLog.user_id == referrer.id,
                AuditLog.action == 'referral_reward',
                AuditLog.description.like(f'%{referred_user.telegram_id}%')
            ).first()
            
            if existing:
                print(f"⏭️ Reward already given for {referred_user.telegram_id} -> {referrer.telegram_id}")
                skipped_count += 1
                continue
            
            # Credit $0.002 to referrer
            reward = Decimal('0.002')
            old_balance = Decimal(referrer.balance or 0)
            old_referral_earnings = Decimal(referrer.referral_earnings_all_time or 0)
            old_total_earnings = Decimal(referrer.total_earnings_all_time or 0)
            
            referrer.balance = old_balance + reward
            referrer.referral_earnings_all_time = old_referral_earnings + reward
            referrer.total_earnings_all_time = old_total_earnings + reward
            
            # Log the reward
            audit = AuditLog(
                user_id=referrer.id,
                action='referral_reward',
                field_changed='balance',
                old_value=float(old_balance),
                new_value=float(referrer.balance),
                amount=float(reward),
                description=f'Referral reward for {referred_user.telegram_id} (wallet + 3 ads) - FIXED',
                source='referral_reward_fix',
                created_at=datetime.utcnow()
            )
            session.add(audit)
            
            credited_count += 1
            print(f"✅ Credited $0.002 to {referrer.telegram_id} for referral {referred_user.telegram_id}")
        
        session.commit()
        
        print("\n" + "="*50)
        print(f"✅ Total credited: {credited_count}")
        print(f"⏭️ Total skipped: {skipped_count}")
        print("="*50)
        
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    fix_missing_referral_rewards()

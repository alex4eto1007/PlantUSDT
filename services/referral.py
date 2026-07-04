import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import User, Investment, ActiveReferral, ReferralUpgrade
from database.db_manager import DatabaseManager
from config.settings import Config

logger = logging.getLogger(__name__)

REFERRAL_TIERS = {
    "free": {"bonus_percent": 1, "price": 0, "emoji": "🌱", "description": "Free"},
    "bronze": {"bonus_percent": 2, "price": 40.00, "emoji": "🥉", "description": "Bronze"},
    "silver": {"bonus_percent": 3, "price": 78.40, "emoji": "🥈", "description": "Silver", "discount": "2%"},
    "gold": {"bonus_percent": 4, "price": 114.00, "emoji": "🥇", "description": "Gold", "discount": "5%"},
    "diamond": {"bonus_percent": 5, "price": 144.00, "emoji": "💎", "description": "Diamond", "discount": "10%"}
}

TIER_ORDER = ["free", "bronze", "silver", "gold", "diamond"]

db = DatabaseManager()

def is_referral_active(user_id: int, session: Session) -> bool:
    """Check if a user qualifies as an active referral"""
    # Check if user has completed at least one investment
    investments = session.query(Investment).filter(
        Investment.user_id == user_id,
        Investment.is_completed == True
    ).count()
    
    if investments > 0:
        return True
    
    # Check if user has watched 50+ ads
    user = session.query(User).filter_by(id=user_id).first()
    if user and (user.total_ads_watched or 0) >= 50:
        return True
    
    return False

def check_and_award_active_referrals(user_id: int, session: Session):
    """Check if any active referrals should be awarded"""
    # Get all pending active referrals for this user
    pending = session.query(ActiveReferral).filter(
        ActiveReferral.referred_user_id == user_id,
        ActiveReferral.status == "pending"
    ).all()
    
    if not pending:
        return
    
    # Check if user is active
    if not is_referral_active(user_id, session):
        return
    
    # Award all pending bonuses
    for referral in pending:
        award_active_referral_bonus(referral.referrer_id, referral.referred_user_id, session)

def award_active_referral_bonus(referrer_id: int, referred_user_id: int, session: Session):
    """Award 0.03 USDT bonus for active referral"""
    # Check if already awarded
    existing = session.query(ActiveReferral).filter(
        ActiveReferral.referrer_id == referrer_id,
        ActiveReferral.referred_user_id == referred_user_id,
        ActiveReferral.status == "awarded"
    ).first()
    
    if existing:
        return False, "Bonus already awarded"
    
    # Get users
    referrer = session.query(User).filter_by(id=referrer_id).first()
    referred = session.query(User).filter_by(id=referred_user_id).first()
    
    if not referrer or not referred:
        return False, "User not found"
    
    # Award bonus
    referrer.balance += 0.03
    referrer.active_referral_bonus_earned = (referrer.active_referral_bonus_earned or 0) + 0.03
    referrer.total_active_referrals = (referrer.total_active_referrals or 0) + 1
    
    # Update referral record
    active_ref = session.query(ActiveReferral).filter(
        ActiveReferral.referrer_id == referrer_id,
        ActiveReferral.referred_user_id == referred_user_id
    ).first()
    
    if active_ref:
        active_ref.status = "awarded"
        active_ref.awarded_at = datetime.utcnow()
    
    session.commit()
    
    logger.info(f"✅ Active referral bonus awarded: {referrer.telegram_id} +0.03 USDT from {referred.telegram_id}")
    
    return True, f"Awarded 0.03 USDT active referral bonus!"

def upgrade_referral_tier(user_id: int, new_tier: str, session: Session) -> tuple:
    """Upgrade user's referral tier"""
    if new_tier not in REFERRAL_TIERS:
        return False, "Invalid tier"
    
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return False, "User not found"
    
    old_tier = user.referral_tier or "free"
    
    # Get tier info
    old_price = REFERRAL_TIERS[old_tier]["price"]
    new_price = REFERRAL_TIERS[new_tier]["price"]
    
    # Check if upgrading to same tier
    if old_tier == new_tier:
        return False, f"You already have {new_tier} tier!"
    
    # Check if downgrading (not allowed)
    if TIER_ORDER.index(new_tier) < TIER_ORDER.index(old_tier):
        return False, "Cannot downgrade tier"
    
    # Calculate upgrade cost (difference between tiers)
    upgrade_cost = new_price - old_price
    
    if upgrade_cost <= 0:
        return False, "Invalid upgrade path"
    
    # Check user balance
    if user.balance < upgrade_cost:
        return False, f"Insufficient balance. Need ${upgrade_cost:.2f} USDT"
    
    # Charge user
    user.balance -= upgrade_cost
    user.referral_tier = new_tier
    user.referral_tier_upgraded_at = datetime.utcnow()
    user.referral_upgrade_total_spent = (user.referral_upgrade_total_spent or 0) + upgrade_cost
    
    # Log upgrade
    upgrade = ReferralUpgrade(
        user_id=user_id,
        tier=new_tier,
        amount_paid=upgrade_cost
    )
    session.add(upgrade)
    session.commit()
    
    logger.info(f"✅ User {user.telegram_id} upgraded to {new_tier} tier (cost: ${upgrade_cost:.2f})")
    
    return True, f"✅ Upgraded to {REFERRAL_TIERS[new_tier]['emoji']} {new_tier.title()} tier! Bonus: {REFERRAL_TIERS[new_tier]['bonus_percent']}%"

def get_referral_stats(user_id: int, session: Session) -> dict:
    """Get referral statistics for a user"""
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        logger.error(f"User {user_id} not found in get_referral_stats")
        return {}
    
    # Get total referred users
    total_referred = session.query(User).filter_by(referred_by=user_id).count()
    
    # Get active referrals count
    active_count = user.total_active_referrals or 0
    
    # Get active bonus earned
    active_bonus = user.active_referral_bonus_earned or 0
    
    # Get pending active referrals
    pending = session.query(ActiveReferral).filter(
        ActiveReferral.referrer_id == user_id,
        ActiveReferral.status == "pending"
    ).count()
    
    # Get tier info
    tier = user.referral_tier or "free"
    tier_info = REFERRAL_TIERS.get(tier, REFERRAL_TIERS["free"])
    
    # Get next tier info
    next_tier = None
    next_price = None
    tier_index = TIER_ORDER.index(tier) if tier in TIER_ORDER else 0
    if tier_index < len(TIER_ORDER) - 1:
        next_tier = TIER_ORDER[tier_index + 1]
        next_price = REFERRAL_TIERS[next_tier]["price"] - REFERRAL_TIERS[tier]["price"]
    
    return {
        "total_referred": total_referred,
        "active_referrals": active_count,
        "active_bonus_earned": active_bonus,
        "pending_active": pending,
        "current_tier": tier,
        "tier_bonus": tier_info["bonus_percent"],
        "tier_emoji": tier_info["emoji"],
        "upgrade_spent": user.referral_upgrade_total_spent or 0,
        "next_tier": next_tier,
        "next_tier_price": next_price,
        "next_tier_bonus": REFERRAL_TIERS[next_tier]["bonus_percent"] if next_tier else None
    }

def get_referral_bonus_percent(user_id: int, session: Session) -> int:
    """Get the referral bonus percentage for a user based on their tier"""
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return 1
    
    tier = user.referral_tier or "free"
    return REFERRAL_TIERS[tier]["bonus_percent"]

def calculate_referral_bonus(amount: float, user_id: int, session: Session) -> float:
    """Calculate referral bonus based on user's tier"""
    bonus_percent = get_referral_bonus_percent(user_id, session)
    return amount * (bonus_percent / 100)

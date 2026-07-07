import logging
from datetime import datetime
from decimal import Decimal
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
    """Check if a user qualifies as an active referral (30 ads OR 1 investment)"""
    investments = session.query(Investment).filter(
        Investment.user_id == user_id,
        Investment.is_completed == True
    ).count()
    
    if investments > 0:
        return True
    
    user = session.query(User).filter_by(id=user_id).first()
    if user and (user.total_ads_watched or 0) >= 30:
        return True
    
    return False

def check_and_award_active_referrals(user_id: int, session: Session):
    """Check if any active referrals should be awarded"""
    pending = session.query(ActiveReferral).filter(
        ActiveReferral.referred_user_id == user_id,
        ActiveReferral.status == "pending"
    ).all()
    
    if not pending:
        return
    
    if not is_referral_active(user_id, session):
        return
    
    for referral in pending:
        award_active_referral_bonus(referral.referrer_id, referral.referred_user_id, session)

def award_active_referral_bonus(referrer_id: int, referred_user_id: int, session: Session):
    """Award 0.03 USDT bonus for active referral"""
    existing = session.query(ActiveReferral).filter(
        ActiveReferral.referrer_id == referrer_id,
        ActiveReferral.referred_user_id == referred_user_id,
        ActiveReferral.status == "awarded"
    ).first()
    
    if existing:
        return False, "Bonus already awarded"
    
    referrer = session.query(User).filter_by(id=referrer_id).first()
    referred = session.query(User).filter_by(id=referred_user_id).first()
    
    if not referrer or not referred:
        return False, "User not found"
    
    bonus = Decimal('0.03')
    referrer.balance = Decimal(str(referrer.balance or 0)) + bonus
    referrer.active_referral_bonus_earned = Decimal(str(referrer.active_referral_bonus_earned or 0)) + bonus
    referrer.total_active_referrals = (referrer.total_active_referrals or 0) + 1
    
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
    
    old_price = Decimal(str(REFERRAL_TIERS[old_tier]["price"]))
    new_price = Decimal(str(REFERRAL_TIERS[new_tier]["price"]))
    
    if old_tier == new_tier:
        return False, f"You already have {new_tier} tier!"
    
    if TIER_ORDER.index(new_tier) < TIER_ORDER.index(old_tier):
        return False, "Cannot downgrade tier"
    
    upgrade_cost = new_price - old_price
    
    if upgrade_cost <= 0:
        return False, "Invalid upgrade path"
    
    user_balance = Decimal(str(user.balance or 0))
    if user_balance < upgrade_cost:
        return False, f"Insufficient balance. Need ${upgrade_cost:.2f} USDT"
    
    user.balance = user_balance - upgrade_cost
    user.referral_tier = new_tier
    user.referral_tier_upgraded_at = datetime.utcnow()
    user.referral_upgrade_total_spent = Decimal(str(user.referral_upgrade_total_spent or 0)) + upgrade_cost
    
    upgrade = ReferralUpgrade(
        user_id=user_id,
        tier=new_tier,
        amount_paid=float(upgrade_cost)
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
    
    total_referred = session.query(User).filter_by(referred_by=user_id).count()
    active_count = user.total_active_referrals or 0
    active_bonus = user.active_referral_bonus_earned or 0
    
    pending = session.query(ActiveReferral).filter(
        ActiveReferral.referrer_id == user_id,
        ActiveReferral.status == "pending"
    ).count()
    
    tier = user.referral_tier or "free"
    tier_info = REFERRAL_TIERS.get(tier, REFERRAL_TIERS["free"])
    
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

# ============================================
# WELCOME BONUS - NO REFERRAL REQUIRED (Task 45)
# ============================================

def award_welcome_bonus(user_id: int, session: Session) -> tuple:
    """Award 0.1 USDT welcome bonus using task system (no referral required)"""
    from services.task_system import claim_task_reward
    from decimal import Decimal
    
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return False, "User not found"
    
    if user.has_received_welcome_bonus:
        logger.info(f"⚠️ User {user_id} already claimed welcome bonus")
        return False, "Welcome bonus already claimed"
    
    if not is_referral_active(user_id, session):
        return False, "You must be active (invest at least once OR watch 30 ads) to claim the welcome bonus."
    
    success, msg = claim_task_reward(user_id, 45, session)
    
    if success:
        user.has_received_welcome_bonus = True
        user.welcome_bonus_claimed_at = datetime.utcnow()
        session.commit()
        logger.info(f"✅ Welcome bonus claimed by user {user_id} via task 45")
        return True, "Welcome bonus of 0.1 USDT awarded!"
    else:
        return False, msg

def get_active_referral_count(user_id: int, session: Session) -> int:
    """Get count of active referrals (users who qualify for 0.03 USDT bonus)"""
    referrals = session.query(User).filter_by(referred_by=user_id).all()
    active_count = 0
    for ref in referrals:
        if is_referral_active(ref.id, session):
            active_count += 1
    return active_count

def get_active_referral_list(user_id: int, session: Session) -> list:
    """Get list of active referrals with details"""
    referrals = session.query(User).filter_by(referred_by=user_id).all()
    active_list = []
    for ref in referrals:
        if is_referral_active(ref.id, session):
            has_invested = session.query(Investment).filter(
                Investment.user_id == ref.id,
                Investment.is_completed == True
            ).count() > 0
            active_list.append({
                'id': ref.id,
                'username': ref.username or ref.first_name or 'User',
                'ads_watched': ref.total_ads_watched or 0,
                'has_invested': has_invested,
                'is_active': True
            })
    return active_list

def get_user_tasks(user_id: int, session: Session) -> dict:
    """Get all tasks for a user with completion status"""
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return {}
    
    tasks = {
        'connect_wallet': {
            'title': '🔗 Connect Wallet',
            'description': 'Connect your Polygon wallet',
            'completed': bool(user.wallet_address),
            'reward': 0
        },
        'first_deposit': {
            'title': '💰 First Deposit',
            'description': 'Deposit at least $5 USDT',
            'completed': user.total_deposited >= 5,
            'reward': 0
        },
        'watch_ads': {
            'title': '📺 Watch Ads',
            'description': f'Watch 30 ads (currently {user.total_ads_watched or 0}/30)',
            'completed': (user.total_ads_watched or 0) >= 30,
            'reward': 0,
            'progress': min((user.total_ads_watched or 0) / 30 * 100, 100)
        },
        'first_investment': {
            'title': '🌱 First Investment',
            'description': 'Plant your first field',
            'completed': user.total_invested > 0,
            'reward': 0
        },
        'refer_a_friend': {
            'title': '👥 Refer a Friend',
            'description': 'Get your first referral',
            'completed': session.query(User).filter_by(referred_by=user_id).count() > 0,
            'reward': 0
        },
        'active_referral_bonus': {
            'title': '🎁 Active Referral Bonus',
            'description': 'Get 0.03 USDT from an active referral',
            'completed': (user.active_referral_bonus_earned or 0) > 0,
            'reward': 0
        }
    }
    
    return tasks

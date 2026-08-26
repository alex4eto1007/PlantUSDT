import logging
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
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
    """Check if a user qualifies as an active referral (must have invested at least once)"""
    investments = session.query(Investment).filter(
        Investment.user_id == user_id
    ).count()
    
    if investments > 0:
        return True
    
    return False


def check_and_award_active_referrals(user_id: int, session: Session):
    """Check if any active referrals should be awarded"""
    try:
        # Get the user to find their referrer
        user = session.query(User).filter_by(id=user_id).first()
        if not user or not user.referred_by:
            return
        
        # Check if this user qualifies as active
        if not is_referral_active(user_id, session):
            return
        
        # Check if already awarded
        existing = session.query(ActiveReferral).filter(
            ActiveReferral.referrer_id == user.referred_by,
            ActiveReferral.referred_user_id == user_id,
            ActiveReferral.status == "awarded"
        ).first()
        
        if existing:
            logger.info(f"Active referral already awarded for user {user_id} to referrer {user.referred_by}")
            return
        
        # Award the bonus
        success, msg = award_active_referral_bonus(user.referred_by, user_id, session)
        if success:
            logger.info(f"✅ Active referral bonus awarded: user {user_id} -> referrer {user.referred_by}")
        else:
            logger.warning(f"⚠️ Failed to award active referral bonus: {msg}")
            
    except Exception as e:
        logger.error(f"Error checking active referrals: {e}")
        session.rollback()


def award_active_referral_bonus(referrer_id: int, referred_user_id: int, session: Session):
    """Award 0.03 USDT bonus for active referral"""
    try:
        # Check if already awarded
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
        
        # Update referrer's balance and all earnings fields
        referrer.balance = (referrer.balance or Decimal('0')) + bonus
        referrer.active_referral_bonus_earned = (referrer.active_referral_bonus_earned or Decimal('0')) + bonus
        referrer.referral_earnings_all_time = (referrer.referral_earnings_all_time or Decimal('0')) + bonus
        referrer.total_earnings_all_time = (referrer.total_earnings_all_time or Decimal('0')) + bonus
        referrer.total_active_referrals = (referrer.total_active_referrals or 0) + 1
        
        # Check if there's an existing pending record
        active_ref = session.query(ActiveReferral).filter(
            ActiveReferral.referrer_id == referrer_id,
            ActiveReferral.referred_user_id == referred_user_id
        ).first()
        
        if active_ref:
            active_ref.status = "awarded"
            active_ref.awarded_at = datetime.utcnow()
        else:
            # Create new record
            new_ref = ActiveReferral(
                referrer_id=referrer_id,
                referred_user_id=referred_user_id,
                bonus_amount=bonus,
                status='awarded',
                awarded_at=datetime.utcnow()
            )
            session.add(new_ref)
        
        session.commit()
        
        logger.info(f"✅ Active referral bonus awarded: referrer {referrer.telegram_id} +0.03 USDT from {referred.telegram_id}")
        logger.info(f"📊 Referrer now has {referrer.total_active_referrals} active referrals")
        
        return True, f"Awarded 0.03 USDT active referral bonus!"
        
    except Exception as e:
        session.rollback()
        logger.error(f"Error awarding active referral bonus: {e}")
        return False, str(e)


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
    
    user_balance = user.balance or Decimal('0')
    if user_balance < upgrade_cost:
        return False, f"Insufficient balance. Need ${upgrade_cost:.2f} USDT"
    
    user.balance = user_balance - upgrade_cost
    user.referral_tier = new_tier
    user.referral_tier_upgraded_at = datetime.utcnow()
    user.referral_upgrade_total_spent = (user.referral_upgrade_total_spent or Decimal('0')) + upgrade_cost
    
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


def award_welcome_bonus(user_id: int, session: Session) -> tuple:
    """Award 0.1 USDT welcome bonus using task system (no referral required)"""
    from services.task_system import claim_task_reward
    
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return False, "User not found"
    
    if user.has_received_welcome_bonus:
        logger.info(f"⚠️ User {user_id} already claimed welcome bonus")
        return False, "Welcome bonus already claimed"
    
    from database.models import UserTaskProgress
    existing = session.query(UserTaskProgress).filter_by(
        user_id=user_id,
        task_id=45,
        claimed=True
    ).first()
    
    if existing:
        user.has_received_welcome_bonus = True
        user.welcome_bonus_claimed_at = datetime.utcnow()
        session.commit()
        logger.info(f"ℹ️ Welcome bonus was already claimed for user {user_id}, marking as received")
        return True, "Welcome bonus already claimed previously!"
    
    success, msg = claim_task_reward(user_id, 45, session)
    
    if success:
        user.has_received_welcome_bonus = True
        user.welcome_bonus_claimed_at = datetime.utcnow()
        session.commit()
        logger.info(f"✅ Welcome bonus claimed by user {user_id} via task 45")
        return True, "Welcome bonus of 0.1 USDT awarded!"
    else:
        if "already claimed" in msg.lower():
            user.has_received_welcome_bonus = True
            user.welcome_bonus_claimed_at = datetime.utcnow()
            session.commit()
            logger.info(f"ℹ️ Welcome bonus was already claimed for user {user_id}, marking as received (from error)")
            return True, "Welcome bonus already claimed!"
        return False, msg


def get_active_referral_count(user_id: int, session: Session) -> int:
    """Get count of active referrals (users who have invested at least once)"""
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
                Investment.user_id == ref.id
            ).count() > 0
            awarded = session.query(ActiveReferral).filter(
                ActiveReferral.referrer_id == user_id,
                ActiveReferral.referred_user_id == ref.id,
                ActiveReferral.status == "awarded"
            ).first() is not None
            active_list.append({
                'id': ref.id,
                'username': ref.username or ref.first_name or 'User',
                'total_invested': float(ref.total_invested or 0),
                'has_invested': has_invested,
                'is_active': True,
                'awarded': awarded
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
            'description': 'Get 0.03 USDT from an active referral (someone who invested)',
            'completed': (user.active_referral_bonus_earned or 0) > 0,
            'reward': 0
        }
    }
    
    return tasks


# ============================================
# ✅ CATCH-UP FUNCTION FOR MISSED ACTIVE REFERRALS
# ============================================

def check_missed_active_referrals():
    """Scan all users and award active referral bonuses that were missed"""
    try:
        session = db.get_session()
        
        # Find all users who have invested at least once
        # and have a referrer, but haven't been awarded yet
        active_users = session.query(User).filter(
            User.referred_by.isnot(None),
            User.total_invested > 0
        ).all()
        
        awarded_count = 0
        for user in active_users:
            # Check if already awarded
            existing = session.query(ActiveReferral).filter(
                ActiveReferral.referrer_id == user.referred_by,
                ActiveReferral.referred_user_id == user.id,
                ActiveReferral.status == "awarded"
            ).first()
            
            if not existing:
                # Award the bonus
                success, msg = award_active_referral_bonus(user.referred_by, user.id, session)
                if success:
                    awarded_count += 1
                    logger.info(f"✅ Catch-up: Awarded active referral bonus for user {user.telegram_id} -> referrer {user.referred_by}")
        
        if awarded_count > 0:
            logger.info(f"✅ Catch-up complete: Awarded {awarded_count} missed active referral bonuses")
        else:
            logger.info("✅ Catch-up: No missed active referrals found")
            
    except Exception as e:
        logger.error(f"Error in check_missed_active_referrals: {e}")
        session.rollback()
    finally:
        session.close()

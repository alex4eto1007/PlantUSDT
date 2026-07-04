REFERRAL_TIERS = {
    "free": {"bonus_percent": 1, "price": 0, "emoji": "🌱"},
    "bronze": {"bonus_percent": 2, "price": 40, "emoji": "🥉"},
    "silver": {"bonus_percent": 3, "price": 78.40, "emoji": "🥈"},
    "gold": {"bonus_percent": 4, "price": 114, "emoji": "🥇"},
    "diamond": {"bonus_percent": 5, "price": 144, "emoji": "💎"}
}

TIER_ORDER = ["free", "bronze", "silver", "gold", "diamond"]

def get_referral_bonus_percent(user_id, session):
    from database.models import User
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return 1
    tier = user.referral_tier or "free"
    return REFERRAL_TIERS.get(tier, REFERRAL_TIERS["free"])["bonus_percent"]

def calculate_referral_bonus(amount, user_id, session):
    bonus_percent = get_referral_bonus_percent(user_id, session)
    return amount * (bonus_percent / 100)

def upgrade_referral_tier(user_id, new_tier, session):
    from database.models import User, ReferralUpgrade
    from datetime import datetime
    
    if new_tier not in REFERRAL_TIERS:
        return False, "Invalid tier"
    
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return False, "User not found"
    
    current_tier = user.referral_tier or "free"
    
    if current_tier == new_tier:
        return False, f"You're already on the {new_tier} tier"
    
    if TIER_ORDER.index(new_tier) < TIER_ORDER.index(current_tier):
        return False, "Cannot downgrade tier"
    
    current_price = REFERRAL_TIERS[current_tier]["price"]
    new_price = REFERRAL_TIERS[new_tier]["price"]
    cost = new_price - current_price
    
    if cost <= 0:
        return False, "Invalid upgrade path"
    
    if user.balance < cost:
        return False, f"Insufficient balance. Need ${cost:.2f}, have ${user.balance:.2f}"
    
    user.balance -= cost
    user.referral_tier = new_tier
    user.referral_tier_upgraded_at = datetime.utcnow()
    user.referral_upgrade_total_spent = (user.referral_upgrade_total_spent or 0) + cost
    
    upgrade = ReferralUpgrade(
        user_id=user.id,
        tier=new_tier,
        amount_paid=cost
    )
    session.add(upgrade)
    session.commit()
    
    return True, f"✅ Upgraded to {REFERRAL_TIERS[new_tier]['emoji']} {new_tier.title()} tier! Bonus: {REFERRAL_TIERS[new_tier]['bonus_percent']}%"

def get_referral_stats(user_id, session):
    from database.models import User, Investment, ActiveReferral
    
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
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
    
    tier_index = TIER_ORDER.index(tier) if tier in TIER_ORDER else 0
    next_tier = None
    next_price = None
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

def check_and_award_active_referrals(user_id, session):
    from database.models import ActiveReferral, Investment, User
    from datetime import datetime
    
    pending = session.query(ActiveReferral).filter(
        ActiveReferral.referred_user_id == user_id,
        ActiveReferral.status == "pending"
    ).all()
    
    if not pending:
        return
    
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return
    
    investments = session.query(Investment).filter(
        Investment.user_id == user_id,
        Investment.is_completed == True
    ).count()
    
    if investments == 0 and (user.total_ads_watched or 0) < 50:
        return
    
    for referral in pending:
        referrer = session.query(User).filter_by(id=referral.referrer_id).first()
        if referrer:
            referrer.balance += 0.03
            referrer.active_referral_bonus_earned = (referrer.active_referral_bonus_earned or 0) + 0.03
            referrer.total_active_referrals = (referrer.total_active_referrals or 0) + 1
            referral.status = "awarded"
            referral.awarded_at = datetime.utcnow()
    
    session.commit()

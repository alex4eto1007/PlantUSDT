REFERRAL_TIERS = {
    "free": {"bonus_percent": 1, "price": 0, "emoji": "🌱"},
    "bronze": {"bonus_percent": 2, "price": 40, "emoji": "🥉"},
    "silver": {"bonus_percent": 3, "price": 78.40, "emoji": "🥈"},
    "gold": {"bonus_percent": 4, "price": 114, "emoji": "🥇"},
    "diamond": {"bonus_percent": 5, "price": 144, "emoji": "💎"}
}

def upgrade_referral_tier(user_id, new_tier, session):
    from database.models import User, ReferralUpgrade
    from datetime import datetime
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return False, "User not found"
    current_tier = user.referral_tier or "free"
    if current_tier == new_tier:
        return False, f"You're already on the {new_tier} tier"
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
    upgrade = ReferralUpgrade(user_id=user.id, tier=new_tier, amount_paid=cost)
    session.add(upgrade)
    session.commit()
    return True, f"✅ Upgraded to {REFERRAL_TIERS[new_tier]['emoji']} {new_tier.title()} tier! Bonus: {REFERRAL_TIERS[new_tier]['bonus_percent']}%"

def get_referral_stats(user_id, session):
    from database.models import User, Investment
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        return None
    referrals = session.query(User).filter_by(referred_by=user.id).all()
    total_referred = len(referrals)
    active_count = 0
    for ref in referrals:
        if ref.total_ads_watched and ref.total_ads_watched >= 50:
            active_count += 1
        else:
            investments = session.query(Investment).filter_by(user_id=ref.id, is_completed=True).count()
            if investments > 0:
                active_count += 1
    pending_active = total_referred - active_count
    active_bonus_earned = user.active_referral_bonus_earned or 0
    upgrade_spent = user.referral_upgrade_total_spent or 0
    current_tier = user.referral_tier or "free"
    tier_info = REFERRAL_TIERS[current_tier]
    tier_list = list(REFERRAL_TIERS.keys())
    current_index = tier_list.index(current_tier)
    next_tier = tier_list[current_index + 1] if current_index + 1 < len(tier_list) else None
    return {
        "current_tier": current_tier,
        "tier_bonus": tier_info["bonus_percent"],
        "tier_emoji": tier_info["emoji"],
        "total_referred": total_referred,
        "active_referrals": active_count,
        "pending_active": pending_active,
        "active_bonus_earned": active_bonus_earned,
        "upgrade_spent": upgrade_spent,
        "next_tier": next_tier,
        "next_tier_bonus": REFERRAL_TIERS[next_tier]["bonus_percent"] if next_tier else None,
        "next_tier_price": REFERRAL_TIERS[next_tier]["price"] - tier_info["price"] if next_tier else None
    }

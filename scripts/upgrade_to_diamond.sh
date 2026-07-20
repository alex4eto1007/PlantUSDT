#!/bin/bash

if [ -z "$1" ]; then
    echo "❌ Usage: ./upgrade_to_diamond.sh USER_ID"
    echo "Example: ./upgrade_to_diamond.sh 123456789"
    exit 1
fi

echo "========================================="
echo "💎 UPGRADING USER TO DIAMOND"
echo "========================================="

# Check if user exists
CURRENT_TIER=$(sudo -u postgres psql -d plantusdt -t -c "SELECT referral_tier FROM users WHERE telegram_id = $1;")

if [ -z "$CURRENT_TIER" ]; then
    echo "❌ User $1 not found!"
    exit 1
fi

echo "📊 Current tier: $CURRENT_TIER"

# Show user stats before upgrade
echo ""
echo "📊 Current stats:"
sudo -u postgres psql -d plantusdt -c "
SELECT 
    telegram_id,
    username,
    referral_tier,
    (SELECT COUNT(*) FROM users WHERE referred_by = u.id) as referrals,
    u.referral_earnings_all_time as earnings
FROM users u
WHERE u.telegram_id = $1;
"

# Confirm upgrade
echo ""
echo "⚠️ Are you sure you want to upgrade $1 to Diamond tier?"
echo "Type 'yes' to confirm:"
read CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Cancelled."
    exit 1
fi

# Upgrade to diamond
sudo -u postgres psql -d plantusdt -c "
UPDATE users 
SET referral_tier = 'diamond',
    referral_tier_upgraded_at = NOW()
WHERE telegram_id = $1;
"

echo ""
echo "✅ User $1 upgraded to Diamond tier!"
echo "📅 Upgraded at: $(date)"

# Show updated info
echo ""
echo "📊 Updated info:"
sudo -u postgres psql -d plantusdt -c "
SELECT 
    telegram_id,
    username,
    referral_tier,
    referral_tier_upgraded_at,
    (SELECT COUNT(*) FROM users WHERE referred_by = u.id) as referrals,
    u.referral_earnings_all_time as earnings
FROM users u
WHERE u.telegram_id = $1;
"

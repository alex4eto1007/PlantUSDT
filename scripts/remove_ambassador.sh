#!/bin/bash

if [ -z "$1" ]; then
    echo "❌ Usage: ./remove_ambassador.sh USER_ID"
    echo "Example: ./remove_ambassador.sh 123456789"
    exit 1
fi

echo "========================================="
echo "⬇️ REMOVING AMBASSADOR STATUS"
echo "========================================="

# Check if user exists
CURRENT_TIER=$(sudo -u postgres psql -d plantusdt -t -c "SELECT referral_tier FROM users WHERE telegram_id = $1;")

if [ -z "$CURRENT_TIER" ]; then
    echo "❌ User $1 not found!"
    exit 1
fi

echo "📊 Current tier: $CURRENT_TIER"

if [ "$CURRENT_TIER" != "diamond" ]; then
    echo "⚠️ User $1 is not an ambassador (current tier: $CURRENT_TIER)"
    exit 1
fi

# Show user stats before removal
echo ""
echo "📊 Current stats:"
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

# Confirm removal
echo ""
echo "⚠️ Are you sure you want to remove $1 from ambassador status?"
echo "This will downgrade them to Free tier (1% bonus)."
echo "Type 'yes' to confirm:"
read CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Cancelled."
    exit 1
fi

# Downgrade to free
sudo -u postgres psql -d plantusdt -c "
UPDATE users 
SET referral_tier = 'free',
    referral_tier_upgraded_at = NULL
WHERE telegram_id = $1;
"

echo ""
echo "✅ User $1 removed from ambassador status!"
echo "📊 New tier: Free (1% bonus)"

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

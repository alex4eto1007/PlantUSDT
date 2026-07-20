#!/bin/bash

echo "========================================="
echo "💎 PLANTUSDT AMBASSADORS (Diamond Tier)"
echo "========================================="
echo ""

sudo -u postgres psql -d plantusdt -c "
SELECT 
    telegram_id,
    username,
    first_name,
    (SELECT COUNT(*) FROM users WHERE referred_by = u.id) as referrals,
    u.referral_earnings_all_time as earnings,
    u.referral_tier_upgraded_at as upgraded_at
FROM users u
WHERE referral_tier = 'diamond'
ORDER BY referral_tier_upgraded_at DESC;
"

echo ""
echo "========================================="
echo "📊 TOTAL AMBASSADORS:"
AMBASSADOR_COUNT=$(sudo -u postgres psql -d plantusdt -t -c "SELECT COUNT(*) FROM users WHERE referral_tier = 'diamond';")
echo "   💎 $AMBASSADOR_COUNT active ambassadors"
echo "========================================="

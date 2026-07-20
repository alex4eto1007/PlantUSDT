#!/bin/bash

echo "========================================="
echo "💎 AMBASSADOR STATUS CHECK"
echo "========================================="
echo ""

AMBASSADORS=$(sudo -u postgres psql -d plantusdt -t -c "SELECT telegram_id FROM users WHERE referral_tier = 'diamond';")

if [ -z "$AMBASSADORS" ]; then
    echo "❌ No ambassadors found."
    exit 1
fi

for ID in $AMBASSADORS; do
    USERNAME=$(sudo -u postgres psql -d plantusdt -t -c "SELECT username FROM users WHERE telegram_id = $ID;")
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "👤 Ambassador: @$USERNAME ($ID)"
    echo ""
    
    sudo -u postgres psql -d plantusdt -c "
    SELECT 
        u.total_invested,
        (SELECT COUNT(*) FROM users WHERE referred_by = u.id) as total_referrals,
        (SELECT COUNT(*) FROM users ref 
         WHERE ref.referred_by = u.id 
         AND (ref.total_ads_watched >= 30 OR ref.total_invested > 0)
        ) as active_referrals,
        EXTRACT(DAY FROM (NOW() - u.created_at)) as days_old,
        u.referral_tier_upgraded_at as upgraded_at,
        u.referral_earnings_all_time as earnings
    FROM users u
    WHERE u.telegram_id = $ID;
    "
    
    echo ""
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 AMBASSADOR REQUIREMENTS:"
echo "   ✅ Active Investment: $300+"
echo "   ✅ Total Referrals: 100+"
echo "   ✅ Active Referrals: 50+ (30 ads OR invested)"
echo "   ✅ Account Age: 14+ days"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

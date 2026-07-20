#!/bin/bash

if [ -z "$1" ]; then
    echo "❌ Usage: ./check_ambassador_candidate.sh USER_ID"
    echo "Example: ./check_ambassador_candidate.sh 123456789"
    exit 1
fi

echo "========================================="
echo "🌱 AMBASSADOR CANDIDATE CHECK"
echo "========================================="

sudo -u postgres psql -d plantusdt -c "
SELECT 
    u.telegram_id,
    u.username,
    u.first_name,
    u.created_at,
    EXTRACT(DAY FROM (NOW() - u.created_at)) as days_old,
    u.total_invested,
    u.total_ads_watched,
    (SELECT COUNT(*) FROM users WHERE referred_by = u.id) as total_referrals,
    (SELECT COUNT(*) FROM users ref 
     WHERE ref.referred_by = u.id 
     AND (ref.total_ads_watched >= 30 OR ref.total_invested > 0)
    ) as active_referrals,
    CASE 
        WHEN u.total_invested >= 300 
        AND (SELECT COUNT(*) FROM users WHERE referred_by = u.id) >= 100
        AND (SELECT COUNT(*) FROM users ref 
             WHERE ref.referred_by = u.id 
             AND (ref.total_ads_watched >= 30 OR ref.total_invested > 0)
            ) >= 50
        AND EXTRACT(DAY FROM (NOW() - u.created_at)) >= 14
        THEN '✅ QUALIFIED'
        ELSE '❌ NOT QUALIFIED'
    END as status,
    CASE 
        WHEN u.total_invested < 300 THEN '❌ Need \$300+ active investment'
        WHEN (SELECT COUNT(*) FROM users WHERE referred_by = u.id) < 100 THEN '❌ Need 100+ referrals'
        WHEN (SELECT COUNT(*) FROM users ref 
              WHERE ref.referred_by = u.id 
              AND (ref.total_ads_watched >= 30 OR ref.total_invested > 0)
             ) < 50 THEN '❌ Need 50+ active referrals'
        WHEN EXTRACT(DAY FROM (NOW() - u.created_at)) < 14 THEN '❌ Need 14+ days old'
        ELSE '✅ All requirements met!'
    END as missing_requirements
FROM users u
WHERE u.telegram_id = $1;
"

echo ""
echo "📋 AMBASSADOR REQUIREMENTS:"
echo "   ✅ Active Investment: \$300+"
echo "   ✅ Total Referrals: 100+"
echo "   ✅ Active Referrals: 50+ (30 ads OR invested)"
echo "   ✅ Account Age: 14+ days"

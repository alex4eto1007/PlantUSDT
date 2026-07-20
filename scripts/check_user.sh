#!/bin/bash

if [ -z "$1" ]; then
    echo "❌ Usage: ./check_user.sh USER_ID"
    echo "Example: ./check_user.sh 123456789"
    exit 1
fi

echo "========================================="
echo "🔍 CHECKING USER: $1"
echo "========================================="

sudo -u postgres psql -d plantusdt -c "
SELECT 
    u.telegram_id,
    u.username,
    u.first_name,
    u.referral_tier,
    (SELECT COUNT(*) FROM users WHERE referred_by = u.id) as total_referrals,
    (SELECT COALESCE(SUM(i.amount), 0) FROM investments i 
     JOIN users ref ON ref.id = i.user_id 
     WHERE ref.referred_by = u.id AND i.is_completed = true) as referral_deposits,
    u.referral_earnings_all_time as referral_earnings,
    u.total_ads_watched as ads_watched,
    u.balance,
    u.created_at
FROM users u
WHERE u.telegram_id = $1;
"

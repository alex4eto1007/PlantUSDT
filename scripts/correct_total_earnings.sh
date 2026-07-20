#!/bin/bash

echo "========================================="
echo "🔄 CORRECTING TOTAL EARNINGS"
echo "========================================="
echo ""
echo "📊 This script will recalculate total_earnings_all_time"
echo "   based on actual earnings from all sources."
echo ""

# Backup first
/root/backup_postgres.sh

echo ""
echo "📊 Recalculating total earnings for all users..."
echo ""

sudo -u postgres psql -d plantusdt -c "
UPDATE users u
SET total_earnings_all_time = (
    COALESCE((SELECT SUM(amount) FROM daily_payouts WHERE user_id = u.id), 0)
    + COALESCE((SELECT SUM(t.reward) FROM user_task_progress utp JOIN tasks t ON utp.task_id = t.id WHERE utp.user_id = u.id AND utp.claimed = true), 0)
    + COALESCE(u.referral_earnings_all_time, 0)
    + COALESCE(u.total_ad_earnings, 0)
);
"

echo ""
echo "✅ Correction complete!"
echo ""

sudo -u postgres psql -d plantusdt -c "
SELECT 
    COUNT(*) as total_users,
    SUM(total_earnings_all_time) as total_earnings_all_users
FROM users;
"

echo ""
echo "📋 To verify a specific user:"
echo "   sudo -u postgres psql -d plantusdt -c \"SELECT telegram_id, username, total_earnings_all_time FROM users WHERE telegram_id = USER_ID;\""

#!/bin/bash

if [ -z "$1" ]; then
    echo "❌ Usage: ./fix_milestone_for_user.sh USER_ID"
    echo "Example: ./fix_milestone_for_user.sh 6988485148"
    exit 1
fi

USER_ID=$1

echo "========================================="
echo "🔧 FIXING MILESTONE FOR USER"
echo "========================================="

# Get current total earnings
TOTAL_EARNINGS=$(sudo -u postgres psql -d plantusdt -t -c "SELECT total_earnings_all_time FROM users WHERE telegram_id = $USER_ID;")

echo "📊 Current total earnings: $TOTAL_EARNINGS"

# Reset milestone tasks (37-44)
sudo -u postgres psql -d plantusdt -c "
UPDATE user_task_progress 
SET completed = false, claimed = false, completed_at = NULL, claimed_at = NULL
WHERE user_id = (SELECT id FROM users WHERE telegram_id = $USER_ID)
AND task_id BETWEEN 37 AND 44;
"

# Recomplete based on current earnings
sudo -u postgres psql -d plantusdt -c "
UPDATE user_task_progress utp
SET completed = true, completed_at = NOW()
FROM users u
WHERE utp.user_id = u.id 
AND u.telegram_id = $USER_ID
AND u.total_earnings_all_time >= (
    CASE 
        WHEN utp.task_id = 37 THEN 1
        WHEN utp.task_id = 38 THEN 10
        WHEN utp.task_id = 39 THEN 25
        WHEN utp.task_id = 40 THEN 50
        WHEN utp.task_id = 41 THEN 100
        WHEN utp.task_id = 42 THEN 250
        WHEN utp.task_id = 43 THEN 500
        WHEN utp.task_id = 44 THEN 1000
    END
)
AND utp.task_id BETWEEN 37 AND 44;
"

echo ""
echo "✅ Milestone fixed for user $USER_ID"
echo "📊 Total earnings: $TOTAL_EARNINGS"
echo ""

sudo -u postgres psql -d plantusdt -c "
SELECT 
    task_id,
    CASE 
        WHEN task_id = 37 THEN 'Earn $1'
        WHEN task_id = 38 THEN 'Earn $10'
        WHEN task_id = 39 THEN 'Earn $25'
        WHEN task_id = 40 THEN 'Earn $50'
        WHEN task_id = 41 THEN 'Earn $100'
        WHEN task_id = 42 THEN 'Earn $250'
        WHEN task_id = 43 THEN 'Earn $500'
        WHEN task_id = 44 THEN 'Earn $1000'
    END as task_name,
    completed,
    claimed
FROM user_task_progress 
WHERE user_id = (SELECT id FROM users WHERE telegram_id = $USER_ID)
AND task_id BETWEEN 37 AND 44
ORDER BY task_id;
"

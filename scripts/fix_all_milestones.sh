#!/bin/bash

echo "========================================="
echo "🔧 FIXING MILESTONES FOR ALL USERS"
echo "========================================="
echo ""

# Backup first
/root/backup_postgres.sh

echo ""
echo "📊 Recalculating total_earnings_all_time for all users..."
echo ""

# 1. Recalculate total_earnings_all_time based on actual earnings
sudo -u postgres psql -d plantusdt -c "
UPDATE users u
SET total_earnings_all_time = (
    COALESCE((SELECT SUM(amount) FROM daily_payouts WHERE user_id = u.id), 0)
    + COALESCE(u.tasks_earnings, 0)
    + COALESCE(u.referral_earnings_all_time, 0)
    + COALESCE(u.total_ad_earnings, 0)
);
"

echo ""
echo "✅ Total earnings recalculated for all users!"
echo ""

# 2. Reset ALL milestone tasks (37-44) for ALL users
echo "🔄 Resetting milestone tasks for all users..."
echo ""

sudo -u postgres psql -d plantusdt -c "
DELETE FROM user_task_progress 
WHERE task_id BETWEEN 37 AND 44;
"

sudo -u postgres psql -d plantusdt -c "
DELETE FROM user_tasks 
WHERE task_id BETWEEN 37 AND 44;
"

echo ""
echo "✅ Milestone tasks reset for all users!"
echo ""

# 3. Recomplete milestone tasks based on current earnings
echo "🔄 Recompleting milestone tasks for all users..."
echo ""

sudo -u postgres psql -d plantusdt -c "
INSERT INTO user_task_progress (user_id, task_id, completed, completed_at)
SELECT 
    u.id,
    t.task_id,
    true,
    NOW()
FROM users u
CROSS JOIN (
    SELECT 37 as task_id, 1 as threshold
    UNION ALL SELECT 38, 10
    UNION ALL SELECT 39, 25
    UNION ALL SELECT 40, 50
    UNION ALL SELECT 41, 100
    UNION ALL SELECT 42, 250
    UNION ALL SELECT 43, 500
    UNION ALL SELECT 44, 1000
) t
WHERE u.total_earnings_all_time >= t.threshold
AND NOT EXISTS (
    SELECT 1 FROM user_task_progress utp 
    WHERE utp.user_id = u.id AND utp.task_id = t.task_id
);
"

echo ""
echo "✅ Milestone tasks recompleted for all users!"
echo ""

# 4. Summary
echo "📊 SUMMARY:"
sudo -u postgres psql -d plantusdt -c "
SELECT 
    COUNT(*) as total_users,
    SUM(total_earnings_all_time) as total_earnings_all_users,
    AVG(total_earnings_all_time) as avg_earnings
FROM users;
"

echo ""
echo "✅ All milestones fixed!"
echo ""
echo "📋 Users can now reopen the Mini App to see correct milestones."

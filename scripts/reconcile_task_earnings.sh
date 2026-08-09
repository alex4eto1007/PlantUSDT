#!/bin/bash

echo "========================================="
echo "🔍 TASK EARNINGS RECONCILIATION"
echo "========================================="
echo ""

sudo -u postgres psql -d plantusdt -c "
SELECT 
    u.telegram_id,
    u.username,
    u.tasks_earnings AS stored_tasks_earnings,
    COALESCE(
        (SELECT SUM(t.reward) FROM user_task_progress utp 
         JOIN tasks t ON utp.task_id = t.id 
         WHERE utp.user_id = u.id AND utp.claimed = true),
        0
    ) AS claimed_task_rewards,
    (SELECT COALESCE(SUM(amount), 0) FROM audit_logs 
     WHERE user_id = u.id 
     AND field_changed = 'tasks_earnings' 
     AND action = 'manual_update') AS manual_adjustments,
    (u.tasks_earnings - COALESCE(
        (SELECT SUM(t.reward) FROM user_task_progress utp 
         JOIN tasks t ON utp.task_id = t.id 
         WHERE utp.user_id = u.id AND utp.claimed = true),
        0
    ) - COALESCE(
        (SELECT COALESCE(SUM(amount), 0) FROM audit_logs 
         WHERE user_id = u.id 
         AND field_changed = 'tasks_earnings' 
         AND action = 'manual_update'),
        0
    )) AS gap
FROM users u
WHERE u.tasks_earnings > 0
AND u.tasks_earnings != COALESCE(
    (SELECT SUM(t.reward) FROM user_task_progress utp 
     JOIN tasks t ON utp.task_id = t.id 
     WHERE utp.user_id = u.id AND utp.claimed = true),
    0
) + COALESCE(
    (SELECT COALESCE(SUM(amount), 0) FROM audit_logs 
     WHERE user_id = u.id 
     AND field_changed = 'tasks_earnings' 
     AND action = 'manual_update'),
    0
);
"

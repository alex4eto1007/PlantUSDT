import logging
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from database.models import User, UserTaskProgress, Investment, AuditLog
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

db = DatabaseManager()

# ============================================
# TASK DEFINITIONS
# ============================================

TASKS = [
    # SECTION 1: INVESTMENTS (7 tasks)
    {"id": 1, "category": "investments", "icon": "🌱", "title": "First Investment", "description": "Invest in any field (any amount)", "reward": 0.01, "condition_type": "first_investment", "condition_value": None},
    {"id": 2, "category": "investments", "icon": "🌱", "title": "Invest $10", "description": "Total invested reaches $10", "reward": 0.02, "condition_type": "total_invested", "condition_value": 10},
    {"id": 3, "category": "investments", "icon": "🌱", "title": "Invest $50", "description": "Total invested reaches $50", "reward": 0.10, "condition_type": "total_invested", "condition_value": 50},
    {"id": 4, "category": "investments", "icon": "🌱", "title": "Invest $100", "description": "Total invested reaches $100", "reward": 0.25, "condition_type": "total_invested", "condition_value": 100},
    {"id": 5, "category": "investments", "icon": "🌱", "title": "Invest $200", "description": "Total invested reaches $200", "reward": 0.60, "condition_type": "total_invested", "condition_value": 200},
    {"id": 6, "category": "investments", "icon": "🌱", "title": "Invest $500", "description": "Total invested reaches $500", "reward": 1.50, "condition_type": "total_invested", "condition_value": 500},
    {"id": 7, "category": "investments", "icon": "🌱", "title": "Invest $1000", "description": "Total invested reaches $1000", "reward": 4.00, "condition_type": "total_invested", "condition_value": 1000},

    # SECTION 2: COMMUNITY TASKS (3 tasks)
    {"id": 27, "category": "community", "icon": "📢", "title": "Join our Channel", "description": "Join @PlantUSDTchannel", "reward": 0.02, "condition_type": "community_task", "condition_value": "channel", "link": "https://t.me/PlantUSDTchannel"},
    {"id": 28, "category": "community", "icon": "💬", "title": "Join our Group", "description": "Join @PlantUSDT", "reward": 0.02, "condition_type": "community_task", "condition_value": "group", "link": "https://t.me/PlantUSDT"},
    {"id": 29, "category": "community", "icon": "📊", "title": "Join Transactions Channel", "description": "Join @PlantUSDTtransactions", "reward": 0.02, "condition_type": "community_task", "condition_value": "transactions", "link": "https://t.me/PlantUSDTtransactions"},

    # SECTION 3: MILESTONES (8 tasks)
    {"id": 37, "category": "milestones", "icon": "🏆", "title": "Earn $1", "description": "Total earnings reach $1", "reward": 0.05, "condition_type": "total_earnings", "condition_value": 1},
    {"id": 38, "category": "milestones", "icon": "🏆", "title": "Earn $10", "description": "Total earnings reach $10", "reward": 0.25, "condition_type": "total_earnings", "condition_value": 10},
    {"id": 39, "category": "milestones", "icon": "🏆", "title": "Earn $25", "description": "Total earnings reach $25", "reward": 0.50, "condition_type": "total_earnings", "condition_value": 25},
    {"id": 40, "category": "milestones", "icon": "🏆", "title": "Earn $50", "description": "Total earnings reach $50", "reward": 1.00, "condition_type": "total_earnings", "condition_value": 50},
    {"id": 41, "category": "milestones", "icon": "🏆", "title": "Earn $100", "description": "Total earnings reach $100", "reward": 1.50, "condition_type": "total_earnings", "condition_value": 100},
    {"id": 42, "category": "milestones", "icon": "🏆", "title": "Earn $250", "description": "Total earnings reach $250", "reward": 3.00, "condition_type": "total_earnings", "condition_value": 250},
    {"id": 43, "category": "milestones", "icon": "🏆", "title": "Earn $500", "description": "Total earnings reach $500", "reward": 5.00, "condition_type": "total_earnings", "condition_value": 500},
    {"id": 44, "category": "milestones", "icon": "🏆", "title": "Earn $1000", "description": "Total earnings reach $1000", "reward": 25.00, "condition_type": "total_earnings", "condition_value": 1000},

    # SECTION 4: WELCOME BONUS (1 task, hidden)
    {"id": 45, "category": "hidden", "icon": "🎁", "title": "Welcome Bonus", "description": "Claim your 0.1 USDT welcome bonus (connect wallet required)", "reward": 0.10, "condition_type": "welcome_bonus", "condition_value": None, "hidden": True}
]

# ============================================
# TASK FUNCTIONS
# ============================================

def get_all_tasks(include_hidden=False):
    if include_hidden:
        return TASKS
    return [task for task in TASKS if not task.get("hidden", False)]

def get_task_by_id(task_id: int):
    for task in TASKS:
        if task["id"] == task_id:
            return task
    return None

def get_user_task_progress(user_id: int, session: Session, include_hidden=False):
    try:
        progress_records = session.query(UserTaskProgress).filter_by(user_id=user_id).all()
        progress_map = {p.task_id: p for p in progress_records}
        result = []
        for task in TASKS:
            if task.get("hidden", False) and not include_hidden:
                continue
            progress = progress_map.get(task["id"])
            if progress:
                result.append({
                    "task_id": task["id"], "title": task["title"],
                    "description": task["description"], "icon": task["icon"],
                    "category": task["category"], "reward": task["reward"],
                    "completed": progress.completed, "claimed": progress.claimed,
                    "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
                    "claimed_at": progress.claimed_at.isoformat() if progress.claimed_at else None
                })
            else:
                result.append({
                    "task_id": task["id"], "title": task["title"],
                    "description": task["description"], "icon": task["icon"],
                    "category": task["category"], "reward": task["reward"],
                    "completed": False, "claimed": False,
                    "completed_at": None, "claimed_at": None
                })
        return result
    except Exception as e:
        logger.error(f"Error getting user task progress: {e}")
        return []

def get_user_stats(user: User, session: Session) -> dict:
    from services.referral import get_active_referral_count
    total_invested = user.total_invested or 0
    total_ads_watched = user.total_ads_watched or 0
    total_referrals = session.query(User).filter_by(referred_by=user.id).count()
    total_active_referrals = get_active_referral_count(user.id, session)
    total_earnings = user.total_earnings_all_time or 0
    has_invested = total_invested > 0
    return {
        "has_invested": has_invested, "total_invested": total_invested,
        "total_ads_watched": total_ads_watched, "total_referrals": total_referrals,
        "total_active_referrals": total_active_referrals, "total_earnings": total_earnings
    }

def check_task_conditions(user: User, session: Session) -> list:
    completed_tasks = []
    total_invested = user.total_invested or 0
    total_ads_watched = user.total_ads_watched or 0
    total_referrals = session.query(User).filter_by(referred_by=user.id).count()
    total_earnings = user.total_earnings_all_time or 0
    has_invested = total_invested > 0

    for task in TASKS:
        # Community tasks are claimed manually — skip auto-completion
        if task["condition_type"] == "community_task":
            continue

        progress = session.query(UserTaskProgress).filter_by(
            user_id=user.id, task_id=task["id"]
        ).first()
        if progress and progress.completed:
            continue

        condition_type = task["condition_type"]
        condition_value = task["condition_value"]
        completed = False

        if condition_type == "first_investment":
            completed = has_invested
        elif condition_type == "total_invested":
            completed = total_invested >= condition_value
        elif condition_type == "total_ads_watched":
            completed = total_ads_watched >= condition_value
        elif condition_type == "total_referrals":
            completed = total_referrals >= condition_value
        elif condition_type == "total_active_referrals":
            from services.referral import get_active_referral_count
            completed = get_active_referral_count(user.id, session) >= condition_value
        elif condition_type == "total_earnings":
            completed = total_earnings >= condition_value
        elif condition_type == "welcome_bonus":
            if not user.has_received_welcome_bonus:
                if user.wallet_address and user.wallet_address != '':
                    completed = True

        if completed:
            if not progress:
                progress = UserTaskProgress(user_id=user.id, task_id=task["id"], completed=False, claimed=False)
                session.add(progress)
                session.flush()
            progress.completed = True
            progress.completed_at = datetime.utcnow()
            completed_tasks.append(task)

    if completed_tasks:
        session.commit()
        logger.info(f"✅ Completed {len(completed_tasks)} tasks for user {user.id}")

    return completed_tasks

def claim_task_reward(user_id: int, task_id: int, session: Session) -> tuple:
    from decimal import Decimal
    try:
        task = get_task_by_id(task_id)
        if not task:
            return False, "Task not found"
        progress = session.query(UserTaskProgress).filter_by(user_id=user_id, task_id=task_id).first()
        if not progress:
            # Community tasks can be claimed even without progress record
            if task["condition_type"] == "community_task":
                progress = UserTaskProgress(user_id=user_id, task_id=task_id, completed=True, claimed=False, completed_at=datetime.utcnow())
                session.add(progress)
                session.flush()
            else:
                return False, "Task not started"
        if not progress.completed:
            return False, "Task not completed yet"
        if progress.claimed:
            return False, "Reward already claimed"
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return False, "User not found"
        reward = Decimal(str(task["reward"]))
        old_value = Decimal(user.tasks_earnings or 0)
        user.balance = (user.balance or Decimal('0')) + reward
        user.tasks_earnings = (user.tasks_earnings or Decimal('0')) + reward
        user.total_earnings_all_time = (user.total_earnings_all_time or Decimal('0')) + reward
        progress.claimed = True
        progress.claimed_at = datetime.utcnow()
        audit = AuditLog(
            user_id=user.id, action='task_claim', field_changed='tasks_earnings',
            old_value=float(old_value), new_value=float(user.tasks_earnings),
            amount=float(reward),
            description=f'Claimed task #{task_id}: {task["title"]}',
            source='task_claim', created_at=datetime.utcnow()
        )
        session.add(audit)
        session.commit()
        logger.info(f"✅ Task {task_id} reward claimed by user {user_id}: +${reward}")
        return True, f"Claimed ${reward:.2f} reward!"
    except Exception as e:
        session.rollback()
        logger.error(f"Error claiming task reward: {e}")
        return False, str(e)

def get_task_stats(user_id: int, session: Session) -> dict:
    try:
        progress_records = session.query(UserTaskProgress).filter_by(user_id=user_id).all()
        visible_task_ids = [task["id"] for task in TASKS if not task.get("hidden", False)]
        total_tasks = len(visible_task_ids)
        completed_tasks = sum(1 for p in progress_records if p.completed and p.task_id in visible_task_ids)
        claimed_tasks = sum(1 for p in progress_records if p.claimed and p.task_id in visible_task_ids)
        total_claimed_amount = Decimal('0')
        for p in progress_records:
            if p.claimed:
                task = get_task_by_id(p.task_id)
                if task:
                    total_claimed_amount += Decimal(str(task["reward"]))
        return {
            "total_tasks": total_tasks, "completed_tasks": completed_tasks,
            "claimed_tasks": claimed_tasks, "total_claimed_amount": float(total_claimed_amount),
            "progress_percentage": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        }
    except Exception as e:
        logger.error(f"Error getting task stats: {e}")
        visible_task_ids = [task["id"] for task in TASKS if not task.get("hidden", False)]
        return {
            "total_tasks": len(visible_task_ids), "completed_tasks": 0,
            "claimed_tasks": 0, "total_claimed_amount": 0, "progress_percentage": 0
        }

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

def create_task(title: str, description: str, reward: float, created_by: int, session: Session) -> tuple:
    """Create a new custom task (admin only)"""
    try:
        from database.models import Task
        task = Task(
            title=title, description=description, reward=Decimal(str(reward)),
            created_by=created_by, is_active=True
        )
        session.add(task)
        session.commit()
        logger.info(f"✅ Custom task created: {title} (${reward})")
        return True, task
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating task: {e}")
        return False, str(e)

def get_all_tasks(session: Session):
    """Get all custom tasks from the DB (admin-facing)"""
    try:
        from database.models import Task
        return session.query(Task).filter_by(is_active=True).all()
    except Exception as e:
        logger.error(f"Error getting all tasks: {e}")
        return []

def get_user_tasks(user_id: int, session: Session) -> dict:
    """Get user tasks (from referral service)"""
    from services.referral import get_user_tasks as get_referral_tasks
    return get_referral_tasks(user_id, session)

def complete_task(user_id: int, task_id: int, session: Session) -> tuple:
    """Mark a custom task as completed for a user (admin tool)"""
    try:
        from database.models import Task, UserTask
        task = session.query(Task).filter_by(id=task_id).first()
        if not task:
            return False, "Task not found"
        user_task = UserTask(
            user_id=user_id, task_id=task_id, completed=True,
            completed_at=datetime.utcnow(), claimed=False
        )
        session.add(user_task)
        session.commit()
        logger.info(f"✅ Task {task_id} completed for user {user_id}")
        return True, "Task completed"
    except Exception as e:
        session.rollback()
        logger.error(f"Error completing task: {e}")
        return False, str(e)

def claim_task_reward(user_id: int, task_id: int, session: Session) -> tuple:
    from decimal import Decimal
    try:
        task = session.query(User).filter_by(id=user_id).first()
        if not task:
            return False, "User not found"
        return False, "Use the API endpoint to claim rewards"
    except Exception as e:
        logger.error(f"Error in claim_task_reward (task_manager): {e}")
        return False, str(e)

def delete_task(task_id: int, session: Session) -> tuple:
    """Delete a custom task (admin only)"""
    try:
        from database.models import Task
        task = session.query(Task).filter_by(id=task_id).first()
        if not task:
            return False, "Task not found"
        task.is_active = False
        session.commit()
        logger.info(f"✅ Task {task_id} deleted")
        return True, "Task deleted"
    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting task: {e}")
        return False, str(e)

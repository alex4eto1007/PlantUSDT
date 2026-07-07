import logging
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from database.models import User, Task, UserTask
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

db = DatabaseManager()

def create_task(title: str, description: str, reward: float, admin_id: int, session: Session) -> tuple:
    """Create a new task"""
    try:
        task = Task(
            title=title,
            description=description,
            reward=Decimal(str(reward)),
            created_by=admin_id,
            created_at=datetime.utcnow(),
            is_active=True
        )
        session.add(task)
        session.commit()
        logger.info(f"✅ Task created: {title} (ID: {task.id})")
        return True, task
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating task: {e}")
        return False, str(e)

def get_all_tasks(session: Session) -> list:
    """Get all active tasks"""
    try:
        tasks = session.query(Task).filter_by(is_active=True).all()
        return tasks
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        return []

def get_user_tasks(user_id: int, session: Session) -> list:
    """Get all tasks for a user with completion status"""
    try:
        tasks = session.query(Task).filter_by(is_active=True).all()
        result = []
        for task in tasks:
            user_task = session.query(UserTask).filter_by(
                user_id=user_id,
                task_id=task.id
            ).first()
            
            completed = user_task.completed if user_task else False
            claimed = user_task.claimed if user_task else False
            completed_at = user_task.completed_at if user_task else None
            
            result.append({
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'reward': float(task.reward),
                'completed': completed,
                'claimed': claimed,
                'completed_at': completed_at.isoformat() if completed_at else None
            })
        return result
    except Exception as e:
        logger.error(f"Error getting user tasks: {e}")
        return []

def complete_task(user_id: int, task_id: int, session: Session) -> tuple:
    """Mark a task as completed for a user"""
    try:
        task = session.query(Task).filter_by(id=task_id, is_active=True).first()
        if not task:
            return False, "Task not found"

        user_task = session.query(UserTask).filter_by(
            user_id=user_id,
            task_id=task_id
        ).first()

        if not user_task:
            user_task = UserTask(
                user_id=user_id,
                task_id=task_id,
                completed=False,
                claimed=False
            )
            session.add(user_task)
            session.flush()

        if user_task.completed:
            return False, "Task already completed"

        user_task.completed = True
        user_task.completed_at = datetime.utcnow()
        session.commit()
        logger.info(f"✅ Task {task_id} completed by user {user_id}")
        return True, "Task completed!"
    except Exception as e:
        session.rollback()
        logger.error(f"Error completing task: {e}")
        return False, str(e)

def claim_task_reward(user_id: int, task_id: int, session: Session) -> tuple:
    """Claim reward for a completed task"""
    try:
        task = session.query(Task).filter_by(id=task_id, is_active=True).first()
        if not task:
            return False, "Task not found"

        user_task = session.query(UserTask).filter_by(
            user_id=user_id,
            task_id=task_id
        ).first()

        if not user_task or not user_task.completed:
            return False, "Task not completed yet"

        if user_task.claimed:
            return False, "Reward already claimed"

        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return False, "User not found"

        # Award reward as Decimal for exact precision
        reward = Decimal(str(task.reward))
        user.balance = Decimal(str(user.balance or 0)) + reward
        user.tasks_earnings = Decimal(str(user.tasks_earnings or 0)) + reward
        user.tasks_completed = (user.tasks_completed or 0) + 1

        user_task.claimed = True
        user_task.claimed_at = datetime.utcnow()

        session.commit()
        logger.info(f"✅ Task {task_id} reward claimed by user {user_id}: +${reward}")
        return True, f"Claimed ${reward:.2f} reward!"
    except Exception as e:
        session.rollback()
        logger.error(f"Error claiming task reward: {e}")
        return False, str(e)

def delete_task(task_id: int, session: Session) -> tuple:
    """Delete a task (soft delete)"""
    try:
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

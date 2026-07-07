import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import User, UserTaskProgress
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

db = DatabaseManager()

# ============================================
# TASK DEFINITIONS - 44 HARDCODED TASKS
# ============================================

TASKS = [
    # ============================================
    # SECTION 1: INVESTMENTS (7 tasks)
    # ============================================
    {
        "id": 1,
        "category": "investments",
        "icon": "🌱",
        "title": "First Investment",
        "description": "Invest in any field (any amount)",
        "reward": 0.01,
        "condition_type": "first_investment",
        "condition_value": None
    },
    {
        "id": 2,
        "category": "investments",
        "icon": "🌱",
        "title": "Invest $10",
        "description": "Total invested reaches $10",
        "reward": 0.02,
        "condition_type": "total_invested",
        "condition_value": 10
    },
    {
        "id": 3,
        "category": "investments",
        "icon": "🌱",
        "title": "Invest $50",
        "description": "Total invested reaches $50",
        "reward": 0.10,
        "condition_type": "total_invested",
        "condition_value": 50
    },
    {
        "id": 4,
        "category": "investments",
        "icon": "🌱",
        "title": "Invest $100",
        "description": "Total invested reaches $100",
        "reward": 0.25,
        "condition_type": "total_invested",
        "condition_value": 100
    },
    {
        "id": 5,
        "category": "investments",
        "icon": "🌱",
        "title": "Invest $200",
        "description": "Total invested reaches $200",
        "reward": 0.60,
        "condition_type": "total_invested",
        "condition_value": 200
    },
    {
        "id": 6,
        "category": "investments",
        "icon": "🌱",
        "title": "Invest $500",
        "description": "Total invested reaches $500",
        "reward": 1.50,
        "condition_type": "total_invested",
        "condition_value": 500
    },
    {
        "id": 7,
        "category": "investments",
        "icon": "🌱",
        "title": "Invest $1000",
        "description": "Total invested reaches $1000",
        "reward": 4.00,
        "condition_type": "total_invested",
        "condition_value": 1000
    },

    # ============================================
    # SECTION 2: ADS (9 tasks) - UPDATED REWARDS
    # ============================================
    {
        "id": 8,
        "category": "ads",
        "icon": "📺",
        "title": "Watch 1 Ad",
        "description": "Watch your first rewarded ad",
        "reward": 0.01,
        "condition_type": "total_ads_watched",
        "condition_value": 1
    },
    {
        "id": 9,
        "category": "ads",
        "icon": "📺",
        "title": "Watch 5 Ads",
        "description": "Watch 5 ads total",
        "reward": 0.02,
        "condition_type": "total_ads_watched",
        "condition_value": 5
    },
    {
        "id": 10,
        "category": "ads",
        "icon": "📺",
        "title": "Watch 10 Ads",
        "description": "Watch 10 ads total",
        "reward": 0.03,
        "condition_type": "total_ads_watched",
        "condition_value": 10
    },
    {
        "id": 11,
        "category": "ads",
        "icon": "📺",
        "title": "Watch 25 Ads",
        "description": "Watch 25 ads total",
        "reward": 0.04,
        "condition_type": "total_ads_watched",
        "condition_value": 25
    },
    {
        "id": 12,
        "category": "ads",
        "icon": "📺",
        "title": "Watch 50 Ads",
        "description": "Watch 50 ads total",
        "reward": 0.05,
        "condition_type": "total_ads_watched",
        "condition_value": 50
    },
    {
        "id": 13,
        "category": "ads",
        "icon": "📺",
        "title": "Watch 100 Ads",
        "description": "Watch 100 ads total",
        "reward": 0.10,
        "condition_type": "total_ads_watched",
        "condition_value": 100
    },
    {
        "id": 14,
        "category": "ads",
        "icon": "📺",
        "title": "Watch 250 Ads",
        "description": "Watch 250 ads total",
        "reward": 0.25,
        "condition_type": "total_ads_watched",
        "condition_value": 250
    },
    {
        "id": 15,
        "category": "ads",
        "icon": "📺",
        "title": "Watch 500 Ads",
        "description": "Watch 500 ads total",
        "reward": 0.60,
        "condition_type": "total_ads_watched",
        "condition_value": 500
    },
    {
        "id": 16,
        "category": "ads",
        "icon": "📺",
        "title": "Watch 1000 Ads",
        "description": "Watch 1,000 ads total",
        "reward": 1.50,
        "condition_type": "total_ads_watched",
        "condition_value": 1000
    },

    # ============================================
    # SECTION 3A: NORMAL REFERRALS (10 tasks)
    # ============================================
    {
        "id": 17,
        "category": "referrals",
        "icon": "👤",
        "title": "Refer 1 Friend",
        "description": "Refer your first friend",
        "reward": 0.02,
        "condition_type": "total_referrals",
        "condition_value": 1
    },
    {
        "id": 18,
        "category": "referrals",
        "icon": "👤",
        "title": "Refer 3 Friends",
        "description": "Refer 3 friends",
        "reward": 0.01,
        "condition_type": "total_referrals",
        "condition_value": 3
    },
    {
        "id": 19,
        "category": "referrals",
        "icon": "👤",
        "title": "Refer 5 Friends",
        "description": "Refer 5 friends",
        "reward": 0.015,
        "condition_type": "total_referrals",
        "condition_value": 5
    },
    {
        "id": 20,
        "category": "referrals",
        "icon": "👤",
        "title": "Refer 10 Friends",
        "description": "Refer 10 friends",
        "reward": 0.02,
        "condition_type": "total_referrals",
        "condition_value": 10
    },
    {
        "id": 21,
        "category": "referrals",
        "icon": "👤",
        "title": "Refer 25 Friends",
        "description": "Refer 25 friends",
        "reward": 0.025,
        "condition_type": "total_referrals",
        "condition_value": 25
    },
    {
        "id": 22,
        "category": "referrals",
        "icon": "👤",
        "title": "Refer 50 Friends",
        "description": "Refer 50 friends",
        "reward": 0.03,
        "condition_type": "total_referrals",
        "condition_value": 50
    },
    {
        "id": 23,
        "category": "referrals",
        "icon": "👤",
        "title": "Refer 100 Friends",
        "description": "Refer 100 friends",
        "reward": 0.05,
        "condition_type": "total_referrals",
        "condition_value": 100
    },
    {
        "id": 24,
        "category": "referrals",
        "icon": "👤",
        "title": "Refer 250 Friends",
        "description": "Refer 250 friends",
        "reward": 0.10,
        "condition_type": "total_referrals",
        "condition_value": 250
    },
    {
        "id": 25,
        "category": "referrals",
        "icon": "👤",
        "title": "Refer 500 Friends",
        "description": "Refer 500 friends",
        "reward": 0.20,
        "condition_type": "total_referrals",
        "condition_value": 500
    },
    {
        "id": 26,
        "category": "referrals",
        "icon": "👤",
        "title": "Refer 1000 Friends",
        "description": "Refer 1,000 friends",
        "reward": 1.00,
        "condition_type": "total_referrals",
        "condition_value": 1000
    },

    # ============================================
    # SECTION 3B: ACTIVE REFERRALS (10 tasks)
    # ============================================
    {
        "id": 27,
        "category": "active_referrals",
        "icon": "👤",
        "title": "1 Active Referral",
        "description": "Have 1 friend become active",
        "reward": 0.05,
        "condition_type": "total_active_referrals",
        "condition_value": 1
    },
    {
        "id": 28,
        "category": "active_referrals",
        "icon": "👤",
        "title": "3 Active Referrals",
        "description": "Have 3 active referrals",
        "reward": 0.03,
        "condition_type": "total_active_referrals",
        "condition_value": 3
    },
    {
        "id": 29,
        "category": "active_referrals",
        "icon": "👤",
        "title": "5 Active Referrals",
        "description": "Have 5 active referrals",
        "reward": 0.10,
        "condition_type": "total_active_referrals",
        "condition_value": 5
    },
    {
        "id": 30,
        "category": "active_referrals",
        "icon": "👤",
        "title": "10 Active Referrals",
        "description": "Have 10 active referrals",
        "reward": 0.14,
        "condition_type": "total_active_referrals",
        "condition_value": 10
    },
    {
        "id": 31,
        "category": "active_referrals",
        "icon": "👤",
        "title": "25 Active Referrals",
        "description": "Have 25 active referrals",
        "reward": 0.20,
        "condition_type": "total_active_referrals",
        "condition_value": 25
    },
    {
        "id": 32,
        "category": "active_referrals",
        "icon": "👤",
        "title": "50 Active Referrals",
        "description": "Have 50 active referrals",
        "reward": 0.30,
        "condition_type": "total_active_referrals",
        "condition_value": 50
    },
    {
        "id": 33,
        "category": "active_referrals",
        "icon": "👤",
        "title": "100 Active Referrals",
        "description": "Have 100 active referrals",
        "reward": 0.50,
        "condition_type": "total_active_referrals",
        "condition_value": 100
    },
    {
        "id": 34,
        "category": "active_referrals",
        "icon": "👤",
        "title": "250 Active Referrals",
        "description": "Have 250 active referrals",
        "reward": 1.00,
        "condition_type": "total_active_referrals",
        "condition_value": 250
    },
    {
        "id": 35,
        "category": "active_referrals",
        "icon": "👤",
        "title": "500 Active Referrals",
        "description": "Have 500 active referrals",
        "reward": 2.00,
        "condition_type": "total_active_referrals",
        "condition_value": 500
    },
    {
        "id": 36,
        "category": "active_referrals",
        "icon": "👤",
        "title": "1000 Active Referrals",
        "description": "Have 1,000 active referrals",
        "reward": 10.00,
        "condition_type": "total_active_referrals",
        "condition_value": 1000
    },

    # ============================================
    # SECTION 4: MILESTONES (8 tasks)
    # ============================================
    {
        "id": 37,
        "category": "milestones",
        "icon": "🏆",
        "title": "Earn $1",
        "description": "Total earnings reach $1",
        "reward": 0.05,
        "condition_type": "total_earnings",
        "condition_value": 1
    },
    {
        "id": 38,
        "category": "milestones",
        "icon": "🏆",
        "title": "Earn $10",
        "description": "Total earnings reach $10",
        "reward": 0.25,
        "condition_type": "total_earnings",
        "condition_value": 10
    },
    {
        "id": 39,
        "category": "milestones",
        "icon": "🏆",
        "title": "Earn $25",
        "description": "Total earnings reach $25",
        "reward": 0.50,
        "condition_type": "total_earnings",
        "condition_value": 25
    },
    {
        "id": 40,
        "category": "milestones",
        "icon": "🏆",
        "title": "Earn $50",
        "description": "Total earnings reach $50",
        "reward": 1.00,
        "condition_type": "total_earnings",
        "condition_value": 50
    },
    {
        "id": 41,
        "category": "milestones",
        "icon": "🏆",
        "title": "Earn $100",
        "description": "Total earnings reach $100",
        "reward": 1.50,
        "condition_type": "total_earnings",
        "condition_value": 100
    },
    {
        "id": 42,
        "category": "milestones",
        "icon": "🏆",
        "title": "Earn $250",
        "description": "Total earnings reach $250",
        "reward": 3.00,
        "condition_type": "total_earnings",
        "condition_value": 250
    },
    {
        "id": 43,
        "category": "milestones",
        "icon": "🏆",
        "title": "Earn $500",
        "description": "Total earnings reach $500",
        "reward": 5.00,
        "condition_type": "total_earnings",
        "condition_value": 500
    },
    {
        "id": 44,
        "category": "milestones",
        "icon": "🏆",
        "title": "Earn $1000",
        "description": "Total earnings reach $1000",
        "reward": 25.00,
        "condition_type": "total_earnings",
        "condition_value": 1000
    }
]

# ============================================
# TASK FUNCTIONS
# ============================================

def get_all_tasks():
    """Get all task definitions"""
    return TASKS

def get_task_by_id(task_id: int):
    """Get a task by its ID"""
    for task in TASKS:
        if task["id"] == task_id:
            return task
    return None

def get_user_task_progress(user_id: int, session: Session) -> dict:
    """Get all tasks with user progress"""
    try:
        # Get existing progress records
        progress_records = session.query(UserTaskProgress).filter_by(user_id=user_id).all()
        progress_map = {p.task_id: p for p in progress_records}
        
        result = []
        for task in TASKS:
            progress = progress_map.get(task["id"])
            if progress:
                result.append({
                    "task_id": task["id"],
                    "title": task["title"],
                    "description": task["description"],
                    "icon": task["icon"],
                    "category": task["category"],
                    "reward": task["reward"],
                    "completed": progress.completed,
                    "claimed": progress.claimed,
                    "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
                    "claimed_at": progress.claimed_at.isoformat() if progress.claimed_at else None
                })
            else:
                result.append({
                    "task_id": task["id"],
                    "title": task["title"],
                    "description": task["description"],
                    "icon": task["icon"],
                    "category": task["category"],
                    "reward": task["reward"],
                    "completed": False,
                    "claimed": False,
                    "completed_at": None,
                    "claimed_at": None
                })
        return result
    except Exception as e:
        logger.error(f"Error getting user task progress: {e}")
        return []

def get_user_stats(user: User, session: Session) -> dict:
    """Get user stats for task progress display - INCLUDES tasks_earnings"""
    from services.referral import is_referral_active, get_active_referral_count
    
    total_invested = user.total_invested or 0
    total_ads_watched = user.total_ads_watched or 0
    total_referrals = session.query(User).filter_by(referred_by=user.id).count()
    total_active_referrals = get_active_referral_count(user.id, session)
    
    # FIX: Include tasks_earnings in total_earnings
    total_earnings = (user.total_earnings_all_time or 0) + (user.referral_earnings_all_time or 0) + (user.total_ad_earnings or 0) + (user.tasks_earnings or 0)
    has_invested = total_invested > 0
    
    return {
        "has_invested": has_invested,
        "total_invested": total_invested,
        "total_ads_watched": total_ads_watched,
        "total_referrals": total_referrals,
        "total_active_referrals": total_active_referrals,
        "total_earnings": total_earnings
    }

def check_task_conditions(user: User, session: Session) -> list:
    """Check all tasks and auto-complete any that are now completed"""
    from services.referral import is_referral_active, get_active_referral_count
    
    completed_tasks = []
    
    # Get user stats
    total_invested = user.total_invested or 0
    total_ads_watched = user.total_ads_watched or 0
    total_referrals = session.query(User).filter_by(referred_by=user.id).count()
    total_active_referrals = get_active_referral_count(user.id, session)
    total_earnings = (user.total_earnings_all_time or 0) + (user.referral_earnings_all_time or 0) + (user.total_ad_earnings or 0) + (user.tasks_earnings or 0)
    
    # Check if user has ever invested (for first_investment)
    has_invested = total_invested > 0
    
    for task in TASKS:
        # Skip if already completed
        progress = session.query(UserTaskProgress).filter_by(
            user_id=user.id,
            task_id=task["id"]
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
            completed = total_active_referrals >= condition_value
        
        elif condition_type == "total_earnings":
            completed = total_earnings >= condition_value
        
        if completed:
            # Mark task as completed
            if not progress:
                progress = UserTaskProgress(
                    user_id=user.id,
                    task_id=task["id"],
                    completed=False,
                    claimed=False
                )
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
    """Claim reward for a completed task"""
    try:
        task = get_task_by_id(task_id)
        if not task:
            return False, "Task not found"
        
        progress = session.query(UserTaskProgress).filter_by(
            user_id=user_id,
            task_id=task_id
        ).first()
        
        if not progress:
            return False, "Task not started"
        
        if not progress.completed:
            return False, "Task not completed yet"
        
        if progress.claimed:
            return False, "Reward already claimed"
        
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return False, "User not found"
        
        # Award reward
        reward = task["reward"]
        user.balance += reward
        user.tasks_earnings = (user.tasks_earnings or 0) + reward
        
        progress.claimed = True
        progress.claimed_at = datetime.utcnow()
        
        session.commit()
        logger.info(f"✅ Task {task_id} reward claimed by user {user_id}: +${reward}")
        return True, f"Claimed ${reward:.2f} reward!"
    except Exception as e:
        session.rollback()
        logger.error(f"Error claiming task reward: {e}")
        return False, str(e)

def get_task_stats(user_id: int, session: Session) -> dict:
    """Get task statistics for a user"""
    try:
        progress_records = session.query(UserTaskProgress).filter_by(user_id=user_id).all()
        total_tasks = len(TASKS)
        completed_tasks = sum(1 for p in progress_records if p.completed)
        claimed_tasks = sum(1 for p in progress_records if p.claimed)
        
        # Calculate total rewards claimed
        total_claimed_amount = 0
        for p in progress_records:
            if p.claimed:
                task = get_task_by_id(p.task_id)
                if task:
                    total_claimed_amount += task["reward"]
        
        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "claimed_tasks": claimed_tasks,
            "total_claimed_amount": total_claimed_amount,
            "progress_percentage": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        }
    except Exception as e:
        logger.error(f"Error getting task stats: {e}")
        return {
            "total_tasks": len(TASKS),
            "completed_tasks": 0,
            "claimed_tasks": 0,
            "total_claimed_amount": 0,
            "progress_percentage": 0
        }

from .investment import InvestmentService
from .scheduler import SchedulerService
from .wallet import WalletService
from .deposit_scanner import DepositScanner
from .notifications import NotificationService
from .referral import (
    upgrade_referral_tier,
    get_referral_stats,
    is_referral_active,
    get_referral_bonus_percent,
    calculate_referral_bonus,
    get_active_referral_count,
    get_active_referral_list,
    award_active_referral_bonus,
    check_and_award_active_referrals,
    award_welcome_bonus,
    get_user_tasks as get_referral_user_tasks
)
from .task_manager import (
    create_task,
    get_all_tasks,
    get_user_tasks,
    complete_task,
    claim_task_reward,
    delete_task
)
from .task_system import (
    get_all_tasks as get_system_tasks,
    get_task_by_id,
    get_user_task_progress,
    get_user_stats,
    check_task_conditions,
    claim_task_reward as system_claim_task_reward,
    get_task_stats,
    TASKS
)

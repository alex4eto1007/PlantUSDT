from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey, Text, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

def generate_unique_code():
    return str(uuid.uuid4())[:8]

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    wallet_address = Column(String(100))
    balance = Column(Numeric(20,6), default=0.0)
    total_invested = Column(Numeric(20,6), default=0.0)
    total_earned = Column(Numeric(20,6), default=0.0)
    total_deposited = Column(Numeric(20,6), default=0.0)
    total_earnings_all_time = Column(Numeric(20,6), default=0.0)
    investment_earnings_all_time = Column(Numeric(20,6), default=0.0)
    referral_earnings_all_time = Column(Numeric(20,6), default=0.0)
    referral_deposit_earnings = Column(Numeric(20,6), default=0.0)
    referred_by = Column(Integer, ForeignKey("users.id"))
    referral_code = Column(String(20), unique=True, default=generate_unique_code)
    referral_earnings = Column(Numeric(20,6), default=0.0)
    can_be_referred = Column(Boolean, default=True)
    referred_at = Column(DateTime, nullable=True)
    ads_watched_today = Column(Integer, default=0)
    last_ad_date = Column(DateTime, nullable=True)
    total_ads_watched = Column(Integer, default=0)
    total_ad_earnings = Column(Numeric(20,6), default=0.0)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_deposit_check = Column(DateTime, default=datetime.utcnow)

    # REFERRAL SYSTEM FIELDS
    referral_tier = Column(String(20), default="free")
    referral_tier_upgraded_at = Column(DateTime, nullable=True)
    referral_upgrade_total_spent = Column(Numeric(20,6), default=0.0)
    active_referral_bonus_earned = Column(Numeric(20,6), default=0.0)
    total_active_referrals = Column(Integer, default=0)

    # NEW FEATURE FIELDS
    interstitial_ads_disabled = Column(Boolean, default=False)
    interstitial_disabled_at = Column(DateTime, nullable=True)
    has_received_welcome_bonus = Column(Boolean, default=False)
    welcome_bonus_claimed_at = Column(DateTime, nullable=True)
    tasks_completed = Column(Integer, default=0)
    last_task_completed_at = Column(DateTime, nullable=True)
    tasks_earnings = Column(Numeric(20,6), default=0.0)

    investments = relationship("Investment", back_populates="user")
    withdrawals = relationship("Withdrawal", back_populates="user")
    deposits = relationship("Deposit", back_populates="user")
    referrals = relationship("User", backref="referrer", remote_side=[id])
    uncollected_fees = relationship("UncollectedFee", back_populates="user")
    referral_upgrades = relationship("ReferralUpgrade", back_populates="user")
    active_referrals_given = relationship("ActiveReferral", foreign_keys="ActiveReferral.referrer_id", back_populates="referrer")
    active_referrals_received = relationship("ActiveReferral", foreign_keys="ActiveReferral.referred_user_id", back_populates="referred_user")
    pending_deposit_checks = relationship("PendingDepositCheck", back_populates="user")
    completed_tasks = relationship("UserTask", back_populates="user")
    task_progress = relationship("UserTaskProgress", back_populates="user")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    reward = Column(Numeric(20,6), default=0.0)
    is_active = Column(Boolean, default=True)
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    user_tasks = relationship("UserTask", back_populates="task")

class UserTask(Base):
    __tablename__ = "user_tasks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    claimed = Column(Boolean, default=False)
    claimed_at = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="completed_tasks")
    task = relationship("Task", back_populates="user_tasks")

class UserTaskProgress(Base):
    __tablename__ = "user_task_progress"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, nullable=False)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)
    claimed = Column(Boolean, default=False)
    claimed_at = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="task_progress")

class Investment(Base):
    __tablename__ = "investments"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    field_number = Column(Integer, nullable=False)
    amount = Column(Numeric(20,6), nullable=False)
    lock_period = Column(Integer, nullable=False, default=30)
    unlock_date = Column(DateTime, nullable=False)
    expected_return = Column(Numeric(20,6), nullable=False)
    paid_out = Column(Numeric(20,6), default=0.0)
    referral_earnings_paid = Column(Numeric(20,6), default=0.0)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=True)
    principal_returned = Column(Boolean, default=False)
    user = relationship("User", back_populates="investments")

class Deposit(Base):
    __tablename__ = "deposits"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Numeric(20,6), nullable=False)
    tx_hash = Column(String(100), unique=True)
    from_address = Column(String(100))
    block_number = Column(BigInteger)
    confirmed_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    network = Column(String(20), default="polygon")
    user = relationship("User", back_populates="deposits")

class DailyPayout(Base):
    __tablename__ = "daily_payouts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    investment_id = Column(Integer, ForeignKey("investments.id"))
    amount = Column(Numeric(20,6), nullable=False)
    day_number = Column(Integer)
    paid_at = Column(DateTime, default=datetime.utcnow)

class Withdrawal(Base):
    __tablename__ = "withdrawals"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Numeric(20,6), nullable=False)
    fee = Column(Numeric(20,6), default=0.0)
    net_amount = Column(Numeric(20,6))
    wallet_address = Column(String(100))
    status = Column(String(20), default="pending")
    tx_hash = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    network = Column(String(20), default="polygon")
    user = relationship("User", back_populates="withdrawals")
    uncollected_fee = relationship("UncollectedFee", back_populates="withdrawal")

class UncollectedFee(Base):
    __tablename__ = "uncollected_fees"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    withdrawal_id = Column(Integer, ForeignKey("withdrawals.id"))
    amount = Column(Numeric(20,6), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    collected = Column(Boolean, default=False)
    collected_at = Column(DateTime, nullable=True)
    tx_hash = Column(String(100), nullable=True)
    user = relationship("User", back_populates="uncollected_fees")
    withdrawal = relationship("Withdrawal", back_populates="uncollected_fee")

class ReferralUpgrade(Base):
    __tablename__ = "referral_upgrades"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tier = Column(String(20), nullable=False)
    amount_paid = Column(Numeric(20,6), nullable=False)
    tx_hash = Column(String(100), nullable=True)
    upgraded_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="referral_upgrades")

class ActiveReferral(Base):
    __tablename__ = "active_referrals"
    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referred_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    bonus_amount = Column(Numeric(20,6), default=0.03)
    awarded_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="pending")
    referrer = relationship("User", foreign_keys=[referrer_id], back_populates="active_referrals_given")
    referred_user = relationship("User", foreign_keys=[referred_user_id], back_populates="active_referrals_received")

class PendingDepositCheck(Base):
    __tablename__ = "pending_deposit_checks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(20,6), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    checked = Column(Boolean, default=False)
    user = relationship("User", back_populates="pending_deposit_checks")

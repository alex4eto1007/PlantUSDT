from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

def generate_unique_code():
    """Generate a unique 8-character referral code"""
    return str(uuid.uuid4())[:8]

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    wallet_address = Column(String(100))
    balance = Column(Float, default=0.0)
    total_invested = Column(Float, default=0.0)
    total_earned = Column(Float, default=0.0)
    total_deposited = Column(Float, default=0.0)
    
    # Earnings tracking
    total_earnings_all_time = Column(Float, default=0.0)
    investment_earnings_all_time = Column(Float, default=0.0)
    referral_earnings_all_time = Column(Float, default=0.0)
    
    # Referral deposit earnings
    referral_deposit_earnings = Column(Float, default=0.0)
    
    # Referral system
    referred_by = Column(Integer, ForeignKey("users.id"))
    referral_code = Column(String(20), unique=True, default=generate_unique_code)
    referral_earnings = Column(Float, default=0.0)
    can_be_referred = Column(Boolean, default=True)
    referred_at = Column(DateTime, nullable=True)
    
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_deposit_check = Column(DateTime, default=datetime.utcnow)
    
    investments = relationship("Investment", back_populates="user")
    withdrawals = relationship("Withdrawal", back_populates="user")
    deposits = relationship("Deposit", back_populates="user")
    referrals = relationship("User", backref="referrer", remote_side=[id])

class Investment(Base):
    __tablename__ = "investments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    field_number = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)
    
    # Lock period settings
    lock_period = Column(Integer, nullable=False, default=30)  # 1, 7, or 30 days
    unlock_date = Column(DateTime, nullable=False)
    expected_return = Column(Float, nullable=False)  # The total amount user will receive
    
    # Payout tracking
    paid_out = Column(Float, default=0.0)
    referral_earnings_paid = Column(Float, default=0.0)
    
    # Dates
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=True)  # True until unlock_date is reached
    principal_returned = Column(Boolean, default=False)
    
    user = relationship("User", back_populates="investments")

class Deposit(Base):
    __tablename__ = "deposits"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    tx_hash = Column(String(100), unique=True)
    from_address = Column(String(100))
    block_number = Column(BigInteger)
    confirmed_at = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    network = Column(String(20), default="polygon")  # Track which network deposit came from
    
    user = relationship("User", back_populates="deposits")

class DailyPayout(Base):
    __tablename__ = "daily_payouts"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    investment_id = Column(Integer, ForeignKey("investments.id"))
    amount = Column(Float, nullable=False)
    day_number = Column(Integer)
    paid_at = Column(DateTime, default=datetime.utcnow)

class Withdrawal(Base):
    __tablename__ = "withdrawals"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    fee = Column(Float, default=0.0)
    net_amount = Column(Float)
    wallet_address = Column(String(100))
    status = Column(String(20), default="pending")
    tx_hash = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    network = Column(String(20), default="polygon")  # Track which network withdrawal was on
    
    user = relationship("User", back_populates="withdrawals")

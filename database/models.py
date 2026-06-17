from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    wallet_address = Column(String(100))
    balance = Column(Float, default=0.0)  # Available balance (rewards + returned principal)
    total_invested = Column(Float, default=0.0)
    total_earned = Column(Float, default=0.0)
    total_deposited = Column(Float, default=0.0)
    referred_by = Column(Integer, ForeignKey("users.id"))
    referral_code = Column(String(20), unique=True, default=lambda: str(uuid.uuid4())[:8])
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # Admin flag
    created_at = Column(DateTime, default=datetime.utcnow)
    last_deposit_check = Column(DateTime, default=datetime.utcnow)
    
    investments = relationship("Investment", back_populates="user")
    withdrawals = relationship("Withdrawal", back_populates="user")
    deposits = relationship("Deposit", back_populates="user")

class Investment(Base):
    __tablename__ = "investments"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    field_number = Column(Integer, nullable=False)  # 1, 2, or 3
    amount = Column(Float, nullable=False)
    daily_rate = Column(Float, default=0.02)  # 2%
    total_return = Column(Float)  # Total expected return (rewards only)
    paid_out = Column(Float, default=0.0)  # Rewards paid so far
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    principal_returned = Column(Boolean, default=False)  # Track if principal was returned
    
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
    amount = Column(Float, nullable=False)  # Original amount requested
    fee = Column(Float, default=0.0)  # 10% fee
    net_amount = Column(Float)  # Amount after fee
    wallet_address = Column(String(100))
    status = Column(String(20), default="pending")  # pending, completed, failed
    tx_hash = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    user = relationship("User", back_populates="withdrawals")
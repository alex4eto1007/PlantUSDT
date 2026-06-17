from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import Config
from database.models import Base, User, Investment, DailyPayout, Withdrawal, Deposit
from datetime import datetime

class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(Config.DATABASE_URL)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
    def get_session(self):
        return self.SessionLocal()
    
    def create_tables(self):
        Base.metadata.create_all(self.engine)
    
    # User operations
    def get_user(self, telegram_id: int):
        with self.get_session() as session:
            return session.query(User).filter_by(telegram_id=telegram_id).first()
    
    def get_user_by_id(self, user_id: int):
        with self.get_session() as session:
            return session.query(User).filter_by(id=user_id).first()
    
    def get_user_by_referral_code(self, referral_code: str):
        with self.get_session() as session:
            return session.query(User).filter_by(referral_code=referral_code).first()
    
    def get_user_by_wallet(self, wallet_address: str):
        with self.get_session() as session:
            return session.query(User).filter_by(wallet_address=wallet_address).first()
    
    def get_all_users(self):
        with self.get_session() as session:
            return session.query(User).all()
    
    def create_user(self, telegram_id: int, username: str, first_name: str, referred_by: int = None):
        with self.get_session() as session:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                referred_by=referred_by
            )
            session.add(user)
            session.commit()
            return user
    
    def update_wallet_address(self, user_id: int, wallet_address: str):
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.wallet_address = wallet_address
                session.commit()
                return user
            return None
    
    def update_balance(self, user_id: int, amount: float):
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.balance += amount
                session.commit()
                return user
            return None
    
    def get_balance(self, user_id: int) -> float:
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            return user.balance if user else 0.0
    
    # Deposit operations
    def process_deposit(self, user_id: int, amount: float, tx_hash: str, from_address: str, block_number: int):
        with self.get_session() as session:
            existing = session.query(Deposit).filter_by(tx_hash=tx_hash).first()
            if existing:
                return None
            
            deposit = Deposit(
                user_id=user_id,
                amount=amount,
                tx_hash=tx_hash,
                from_address=from_address,
                block_number=block_number,
                processed=True
            )
            session.add(deposit)
            
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.balance += amount
                user.total_deposited += amount
                user.last_deposit_check = datetime.utcnow()
            
            session.commit()
            return deposit
    
    def get_user_deposits(self, user_id: int):
        with self.get_session() as session:
            return session.query(Deposit).filter_by(user_id=user_id).all()
    
    def update_last_deposit_check(self, user_id: int):
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.last_deposit_check = datetime.utcnow()
                session.commit()
    
    # Investment operations
    def create_investment(self, user_id: int, amount: float):
        with self.get_session() as session:
            total_return = amount * (1 + 0.02 * 30)
            investment = Investment(
                user_id=user_id,
                amount=amount,
                total_return=total_return
            )
            session.add(investment)
            
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.total_invested += amount
            
            session.commit()
            return investment
    
    def get_active_investments(self):
        with self.get_session() as session:
            return session.query(Investment).filter_by(is_active=True, is_completed=False).all()
    
    def get_user_investments(self, user_id: int):
        with self.get_session() as session:
            return session.query(Investment).filter_by(user_id=user_id).all()
    
    # Payout operations
    def record_payout(self, user_id: int, investment_id: int, amount: float, day_number: int):
        with self.get_session() as session:
            payout = DailyPayout(
                user_id=user_id,
                investment_id=investment_id,
                amount=amount,
                day_number=day_number
            )
            session.add(payout)
            
            investment = session.query(Investment).filter_by(id=investment_id).first()
            if investment:
                investment.paid_out += amount
                if investment.paid_out >= investment.total_return:
                    investment.is_completed = True
                    investment.is_active = False
            
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.balance += amount
                user.total_earned += amount
            
            session.commit()
            return payout
    
    # Withdrawal operations
    def create_withdrawal(self, user_id: int, amount: float, wallet_address: str):
        with self.get_session() as session:
            fee = amount * 0.10
            net_amount = amount - fee
            
            withdrawal = Withdrawal(
                user_id=user_id,
                amount=amount,
                fee=fee,
                net_amount=net_amount,
                wallet_address=wallet_address
            )
            session.add(withdrawal)
            
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.balance -= amount
            
            session.commit()
            return withdrawal
    
    def update_withdrawal_status(self, withdrawal_id: int, status: str, tx_hash: str = None):
        with self.get_session() as session:
            withdrawal = session.query(Withdrawal).filter_by(id=withdrawal_id).first()
            if withdrawal:
                withdrawal.status = status
                if tx_hash:
                    withdrawal.tx_hash = tx_hash
                if status in ["completed", "failed"]:
                    withdrawal.processed_at = datetime.utcnow()
                session.commit()
                return withdrawal
            return None
    
    def get_pending_withdrawals(self):
        with self.get_session() as session:
            return session.query(Withdrawal).filter_by(status="pending").all()
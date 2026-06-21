from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from config.settings import Config
from database.models import Base, User, Investment, Deposit, DailyPayout, Withdrawal
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.engine = None
        self.Session = None
        self._init_engine()

    def _init_engine(self):
        """Initialize database engine with connection pooling"""
        try:
            # Get database URL from config
            database_url = Config.DATABASE_URL
            
            # Create engine with connection pooling settings
            self.engine = create_engine(
                database_url,
                pool_size=10,              # Increased from default 5
                max_overflow=20,           # Increased from default 10
                pool_timeout=60,           # Increased from default 30
                pool_recycle=3600,         # Recycle connections after 1 hour
                pool_pre_ping=True,        # Check connection before using
                echo=False,
                poolclass=QueuePool
            )
            
            # Create session factory
            self.Session = scoped_session(
                sessionmaker(
                    bind=self.engine,
                    autocommit=False,
                    autoflush=False,
                    expire_on_commit=False
                )
            )
            
            logger.info(f"Database engine initialized with pool_size=10, max_overflow=20")
            
        except Exception as e:
            logger.error(f"Error initializing database engine: {e}")
            raise

    def get_session(self):
        """Get a new database session"""
        try:
            return self.Session()
        except Exception as e:
            logger.error(f"Error getting database session: {e}")
            raise

    def create_tables(self):
        """Create all tables"""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise

    def get_user(self, telegram_id):
        """Get user by telegram_id"""
        session = self.get_session()
        try:
            return session.query(User).filter_by(telegram_id=telegram_id).first()
        finally:
            session.close()

    def get_user_by_id(self, user_id):
        """Get user by database id"""
        session = self.get_session()
        try:
            return session.query(User).filter_by(id=user_id).first()
        finally:
            session.close()

    def get_user_by_referral_code(self, referral_code):
        """Get user by referral code"""
        session = self.get_session()
        try:
            return session.query(User).filter_by(referral_code=referral_code).first()
        finally:
            session.close()

    def create_user(self, telegram_id, username=None, first_name=None, referred_by=None):
        """Create a new user"""
        session = self.get_session()
        try:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                referred_by=referred_by
            )
            session.add(user)
            session.commit()
            logger.info(f"User {telegram_id} created successfully")
            return user
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating user: {e}")
            raise
        finally:
            session.close()

    def get_pending_withdrawals(self):
        """Get all pending withdrawals"""
        session = self.get_session()
        try:
            return session.query(Withdrawal).filter_by(status='pending').all()
        finally:
            session.close()

    def get_withdrawal_by_id(self, withdrawal_id):
        """Get withdrawal by id"""
        session = self.get_session()
        try:
            return session.query(Withdrawal).filter_by(id=withdrawal_id).first()
        finally:
            session.close()

    def update_withdrawal_status(self, withdrawal_id, status, tx_hash=None):
        """Update withdrawal status"""
        session = self.get_session()
        try:
            withdrawal = session.query(Withdrawal).filter_by(id=withdrawal_id).first()
            if withdrawal:
                withdrawal.status = status
                if tx_hash:
                    withdrawal.tx_hash = tx_hash
                withdrawal.processed_at = datetime.utcnow()
                session.commit()
                logger.info(f"Withdrawal {withdrawal_id} updated to {status}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating withdrawal: {e}")
            return False
        finally:
            session.close()

    def reset_user_referral(self, user_id):
        """Reset a user's referral status"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.can_be_referred = True
                user.referred_by = None
                user.referred_at = None
                session.commit()
                logger.info(f"Referral reset for user {user_id}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error resetting referral: {e}")
            return False
        finally:
            session.close()

    def get_user_by_telegram_id(self, telegram_id):
        """Get user by telegram_id (alias for get_user)"""
        return self.get_user(telegram_id)

    def get_deposits_by_user(self, user_id):
        """Get all deposits for a user"""
        session = self.get_session()
        try:
            return session.query(Deposit).filter_by(user_id=user_id).all()
        finally:
            session.close()

    def get_payouts_by_user(self, user_id):
        """Get all payouts for a user"""
        session = self.get_session()
        try:
            return session.query(DailyPayout).filter_by(user_id=user_id).all()
        finally:
            session.close()

    def get_investments_by_user(self, user_id):
        """Get all investments for a user"""
        session = self.get_session()
        try:
            return session.query(Investment).filter_by(user_id=user_id).all()
        finally:
            session.close()

    def get_active_investments_by_user(self, user_id):
        """Get all active investments for a user"""
        session = self.get_session()
        try:
            return session.query(Investment).filter_by(user_id=user_id, is_active=True).all()
        finally:
            session.close()

    def get_referrals_by_user(self, user_id):
        """Get all referrals for a user"""
        session = self.get_session()
        try:
            return session.query(User).filter_by(referred_by=user_id).all()
        finally:
            session.close()

    def get_referral_count(self, user_id):
        """Get referral count for a user"""
        session = self.get_session()
        try:
            return session.query(User).filter_by(referred_by=user_id).count()
        finally:
            session.close()

    def update_user_balance(self, user_id, amount):
        """Update user balance"""
        session = self.get_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.balance += amount
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating user balance: {e}")
            return False
        finally:
            session.close()

    def close_all_sessions(self):
        """Close all sessions (for cleanup)"""
        try:
            self.Session.remove()
            logger.info("All sessions closed")
        except Exception as e:
            logger.error(f"Error closing sessions: {e}")

    def dispose_engine(self):
        """Dispose the engine (for cleanup)"""
        try:
            if self.engine:
                self.engine.dispose()
                logger.info("Engine disposed")
        except Exception as e:
            logger.error(f"Error disposing engine: {e}")

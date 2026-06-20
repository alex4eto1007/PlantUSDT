from database.models import Base
from database.db_manager import DatabaseManager

print("Creating tables...")
Base.metadata.create_all(DatabaseManager().engine)
print("✅ Tables created successfully!")

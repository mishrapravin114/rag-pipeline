
import os
import sys
from sqlalchemy import create_engine, text

# Add parent directory to path to import settings
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config.settings import settings

def upgrade():
    """Apply the migration."""
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as connection:
        connection.execute(text("""
            ALTER TABLE `Users`
            ADD COLUMN google_access_token TEXT,
            ADD COLUMN google_refresh_token TEXT,
            ADD COLUMN google_token_expiry DATETIME;
        """))
    print("Migration applied successfully.")

if __name__ == "__main__":
    upgrade()

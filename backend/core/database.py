import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

# We load the DATABASE_URL from .env or environment variables.
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:pWkejwZmBik1tMYr@db.uniqqsjwsqnboeuzhdyf.supabase.co:5432/postgres")

engine = create_engine(DB_URL, pool_size=5, max_overflow=10)

def get_db_connection():
    return engine.connect()

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models_sql import Base
from dotenv import load_dotenv

load_dotenv()

# Use SQLite for local dev if no URL provided, but warn user
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./research_app.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

import os
from models import Chat, User
from sqlmodel import SQLModel, Session, create_engine, select

import bcrypt

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./newsfoundry.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=True, connect_args=connect_args)



def init_db():
    SQLModel.metadata.create_all(engine)
    print("Database initialized successfully")

    # Ensure columns press_review and loaded_articles exist in chat table
    with Session(engine) as session:
        try:
            from sqlalchemy import text
            session.exec(text("ALTER TABLE chat ADD COLUMN IF NOT EXISTS press_review JSON;"))
            session.exec(text("ALTER TABLE chat ADD COLUMN IF NOT EXISTS loaded_articles JSON DEFAULT '[]'::json;"))
            session.commit()
        except Exception:
            session.rollback()

    # Creating or repairing default user
    default_email = "test@test.com"
    default_password = "test"
    clean_hash = bcrypt.hashpw(default_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    with Session(engine) as session:
        statement = select(User).where(User.email == default_email)
        user = session.exec(statement).first()

        if not user:
            session.add(
                User(
                    email=default_email,
                    hashed_password=clean_hash,
                )
            )
            session.commit()
        elif user.hashed_password.startswith("\\x"):
            user.hashed_password = clean_hash
            session.add(user)
            session.commit()



def get_session():
    with Session(engine) as session:
        yield session


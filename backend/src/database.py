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
    with engine.begin() as conn:
        from sqlalchemy import inspect, text
        inspector = inspect(conn)
        existing_columns = [col["name"] for col in inspector.get_columns("chat")] if inspector.has_table("chat") else []

        if "press_review" not in existing_columns:
            try:
                conn.execute(text("ALTER TABLE chat ADD COLUMN press_review JSON;"))
            except Exception as e:
                print(f"Migration note (press_review): {e}")

        if "loaded_articles" not in existing_columns:
            try:
                if engine.dialect.name == "postgresql":
                    conn.execute(text("ALTER TABLE chat ADD COLUMN loaded_articles JSON DEFAULT '[]'::json;"))
                else:
                    conn.execute(text("ALTER TABLE chat ADD COLUMN loaded_articles JSON DEFAULT '[]';"))
            except Exception as e:
                print(f"Migration note (loaded_articles): {e}")

        # Ensure no existing rows have NULL for loaded_articles
        try:
            if engine.dialect.name == "postgresql":
                conn.execute(text("UPDATE chat SET loaded_articles = '[]'::json WHERE loaded_articles IS NULL;"))
            else:
                conn.execute(text("UPDATE chat SET loaded_articles = '[]' WHERE loaded_articles IS NULL;"))
        except Exception as e:
            print(f"Migration note (loaded_articles update): {e}")

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


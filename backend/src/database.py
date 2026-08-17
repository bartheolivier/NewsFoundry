import os
from models import User
from sqlmodel import SQLModel, Session, create_engine, select
import bcrypt

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./newsfoundry.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=True, connect_args=connect_args)



def init_db():
    SQLModel.metadata.create_all(engine)
    print("Database initialized successfully")

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


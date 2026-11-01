import os
from pathlib import Path
from dotenv import load_dotenv
from models import Chat, User
from sqlmodel import SQLModel, Session, create_engine, select

import bcrypt

# Charge automatiquement le fichier .env s'il est présent
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

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

        if "system_prompt" not in existing_columns:
            try:
                conn.execute(text("ALTER TABLE chat ADD COLUMN system_prompt TEXT;"))
            except Exception as e:
                print(f"Migration note (system_prompt): {e}")

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

    # Creating or synchronizing default/demo user from environment variables
    seed_default_user(engine)


def seed_default_user(target_engine=None) -> None:
    """Crée ou synchronise le compte utilisateur initial à partir des variables d'environnement.

    En local (par défaut) : test@test.com / test.
    En production (Railway) : définir DEMO_USER_EMAIL et DEMO_USER_PASSWORD met à jour
    automatiquement le hachage en base et désactive le mot de passe par défaut 'test'.
    """
    db_engine = target_engine or engine
    default_email = os.getenv("DEMO_USER_EMAIL", "test@test.com").strip() or "test@test.com"
    default_password = os.getenv("DEMO_USER_PASSWORD", "test")
    clean_hash = bcrypt.hashpw(default_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    with Session(db_engine) as session:
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
        else:
            needs_update = user.hashed_password.startswith("\\x")
            if not needs_update:
                try:
                    needs_update = not bcrypt.checkpw(
                        default_password.encode("utf-8"),
                        user.hashed_password.encode("utf-8"),
                    )
                except Exception:
                    needs_update = True
            if needs_update:
                user.hashed_password = clean_hash
                session.add(user)
                session.commit()

        # Si un email personnalisé et un mot de passe fort sont définis en production,
        # neutraliser l'éventuel ancien compte test@test.com s'il utilisait encore 'test'
        if default_email != "test@test.com" and default_password != "test":
            legacy_user = session.exec(select(User).where(User.email == "test@test.com")).first()
            if legacy_user:
                try:
                    still_weak = bcrypt.checkpw(b"test", legacy_user.hashed_password.encode("utf-8"))
                except Exception:
                    still_weak = True
                if still_weak:
                    legacy_user.hashed_password = clean_hash
                    session.add(legacy_user)
                    session.commit()



def get_session():
    with Session(engine) as session:
        yield session


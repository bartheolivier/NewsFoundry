import sys
from pathlib import Path

# Add src to python path
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from database import get_session
from main import app
from models import User


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(name="session")
def session_fixture():

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    # Insert default test user
    with Session(engine) as session:
        default_email = "test@test.com"
        default_password = "test"
        session.add(
            User(
                email=default_email,
                hashed_password=bcrypt.hashpw(
                    default_password.encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8"),
            )
        )
        session.commit()

    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

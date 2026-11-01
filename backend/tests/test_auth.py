from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "👋"


def test_login_success(client: TestClient):
    response = client.post(
        "/login",
        json={"email": "test@test.com", "password": "test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "test@test.com"


def test_login_invalid_password(client: TestClient):
    response = client.post(
        "/login",
        json={"email": "test@test.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Email ou mot de passe incorrect" in response.json()["detail"]


def test_login_nonexistent_user(client: TestClient):
    response = client.post(
        "/login",
        json={"email": "nonexistent@test.com", "password": "test"},
    )
    assert response.status_code == 401
    assert "Email ou mot de passe incorrect" in response.json()["detail"]


def test_get_me_authenticated(client: TestClient):
    login_res = client.post(
        "/login",
        json={"email": "test@test.com", "password": "test"},
    )
    token = login_res.json()["access_token"]

    response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@test.com"


def test_get_me_unauthorized(client: TestClient):
    response = client.get("/me")
    assert response.status_code == 401
    assert "Token d'authentification manquant" in response.json()["detail"]


def test_get_me_invalid_token(client: TestClient):
    response = client.get(
        "/me",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert response.status_code == 401
    assert "Token invalide ou expiré" in response.json()["detail"]


def test_seed_default_user_custom_credentials_updates_existing_password(monkeypatch):
    """Vérifie que DEMO_USER_PASSWORD met à jour un compte existant et invalide l'ancien mot de passe 'test'."""
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool

    from auth import verify_password
    from database import seed_default_user
    from models import User

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)

    # 1. Initialisation avec les valeurs par défaut (test@test.com / test)
    monkeypatch.delenv("DEMO_USER_EMAIL", raising=False)
    monkeypatch.delenv("DEMO_USER_PASSWORD", raising=False)
    seed_default_user(test_engine)

    with Session(test_engine) as s:
        u = s.exec(select(User).where(User.email == "test@test.com")).first()
        assert u is not None
        assert verify_password("test", u.hashed_password)

    # 2. Rotation du mot de passe en production via DEMO_USER_PASSWORD
    monkeypatch.setenv("DEMO_USER_PASSWORD", "SecretJury2026!")
    seed_default_user(test_engine)

    with Session(test_engine) as s:
        u = s.exec(select(User).where(User.email == "test@test.com")).first()
        assert u is not None
        assert not verify_password("test", u.hashed_password)
        assert verify_password("SecretJury2026!", u.hashed_password)


def test_seed_default_user_custom_email_rotates_legacy_test_user(monkeypatch):
    """Vérifie que définir DEMO_USER_EMAIL + DEMO_USER_PASSWORD crée le compte dédié et désactive 'test' sur test@test.com."""
    from sqlmodel import Session, SQLModel, create_engine, select
    from sqlmodel.pool import StaticPool

    from auth import verify_password
    from database import seed_default_user
    from models import User

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)

    monkeypatch.delenv("DEMO_USER_EMAIL", raising=False)
    monkeypatch.delenv("DEMO_USER_PASSWORD", raising=False)
    seed_default_user(test_engine)

    monkeypatch.setenv("DEMO_USER_EMAIL", "jury@newsfoundry.fr")
    monkeypatch.setenv("DEMO_USER_PASSWORD", "CoffreFort#2026")
    seed_default_user(test_engine)

    with Session(test_engine) as s:
        jury_user = s.exec(select(User).where(User.email == "jury@newsfoundry.fr")).first()
        legacy_user = s.exec(select(User).where(User.email == "test@test.com")).first()
        assert jury_user is not None
        assert verify_password("CoffreFort#2026", jury_user.hashed_password)
        assert legacy_user is not None
        assert not verify_password("test", legacy_user.hashed_password)


def test_login_rate_limiting_blocks_bruteforce(client: TestClient, monkeypatch):
    """Vérifie que les tentatives répétées de connexion échouées sont bloquées en HTTP 429."""
    monkeypatch.setenv("MAX_LOGIN_ATTEMPTS", "3")

    for _ in range(3):
        res = client.post("/login", json={"email": "test@test.com", "password": "wrong"})
        assert res.status_code == 401

    blocked_res = client.post("/login", json={"email": "test@test.com", "password": "wrong"})
    assert blocked_res.status_code == 429
    assert "Trop de tentatives" in blocked_res.json()["detail"]


def test_daily_ai_quota_cap_protects_billing(client: TestClient, monkeypatch):
    """Vérifie que MAX_DAILY_AI_CALLS bloque les appels IA excédentaires en HTTP 429 pour protéger la facturation."""
    from unittest.mock import AsyncMock

    monkeypatch.setenv("MAX_DAILY_AI_CALLS", "1")
    monkeypatch.setattr("main.get_top_news_api", AsyncMock(return_value=[]))
    monkeypatch.setattr("main.run_chat_agent", AsyncMock(return_value=("Réponse test", [])))

    login_res = client.post("/login", json={"email": "test@test.com", "password": "test"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    chat_res = client.post("/chats", headers=headers)
    chat_id = chat_res.json()["id"]

    # 1er appel autorisé
    res1 = client.post(f"/chats/{chat_id}/messages", json={"content": "Bonjour"}, headers=headers)
    assert res1.status_code == 200

    # 2e appel bloqué par le plafond quotidien
    res2 = client.post(f"/chats/{chat_id}/messages", json={"content": "Encore une question"}, headers=headers)
    assert res2.status_code == 429
    assert "Plafond quotidien" in res2.json()["detail"]

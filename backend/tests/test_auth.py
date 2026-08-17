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

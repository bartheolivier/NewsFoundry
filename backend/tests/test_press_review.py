from unittest.mock import AsyncMock, patch
import bcrypt
from fastapi.testclient import TestClient
from sqlmodel import Session

from models import ArticleSummary, PressReviewOutput, User


def get_token_for_user(client: TestClient, email: str = "test@test.com", password: str = "test") -> str:
    response = client.post("/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def create_second_user(session: Session) -> User:
    user2 = User(
        email="second@test.com",
        hashed_password=bcrypt.hashpw(b"test2", bcrypt.gensalt()).decode("utf-8"),
    )
    session.add(user2)
    session.commit()
    session.refresh(user2)
    return user2


MOCK_PRESS_REVIEW_OUTPUT = PressReviewOutput(
    title="REVUE DE PRESSE : VOITURES ÉLECTRIQUES EN FRANCE",
    topic="Véhicules électriques",
    general_summary="Le marché français de l'électrique poursuit son expansion malgré des freins tarifaires.",
    articles=[
        ArticleSummary(
            title="L'Aveyron passe à la voiture électrique",
            source="Midi Libre",
            url="https://example.com/aveyron-ve",
            summary="Une transition progressive constatée dans les zones rurales.",
        )
    ],
    perspectives="L'extension des bornes de recharge sera déterminante pour 2027.",
)


def test_generate_press_review_success(client: TestClient):
    token = get_token_for_user(client)

    # 1. Create a chat
    create_res = client.post(
        "/chats",
        json={"title": "Enquête Mobilité"},
        headers={"Authorization": f"Bearer {token}"},
    )
    chat_id = create_res.json()["id"]

    # 2. Add a message to chat
    with patch("main.run_chat_agent", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = "Voici les actualités sur les VE..."
        client.post(
            f"/chats/{chat_id}/messages",
            json={"content": "Quelles sont les nouvelles sur les voitures électriques ?"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # 3. Generate press review
    with patch("main.generate_press_review", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_PRESS_REVIEW_OUTPUT

        res = client.post(
            f"/chats/{chat_id}/press-review",
            json={"topic": "Véhicules électriques"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert res.status_code == 200
        data = res.json()
        assert "press_review" in data
        assert data["press_review"] is not None
        assert data["press_review"]["title"] == "REVUE DE PRESSE : VOITURES ÉLECTRIQUES EN FRANCE"
        assert len(data["press_review"]["articles"]) == 1
        assert data["press_review"]["articles"][0]["title"] == "L'Aveyron passe à la voiture électrique"
        assert "generated_at" in data["press_review"]

    # 4. Verify persistence in GET /chats/{chat_id}
    get_res = client.get(f"/chats/{chat_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 200
    assert get_res.json()["press_review"]["title"] == "REVUE DE PRESSE : VOITURES ÉLECTRIQUES EN FRANCE"


def test_generate_press_review_empty_chat_fails(client: TestClient):
    token = get_token_for_user(client)
    create_res = client.post(
        "/chats",
        json={"title": "Chat tout neuf vide"},
        headers={"Authorization": f"Bearer {token}"},
    )
    chat_id = create_res.json()["id"]

    res = client.post(
        f"/chats/{chat_id}/press-review",
        json={"topic": "Intelligence Artificielle"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "vide" in res.json()["detail"]


def test_generate_press_review_empty_topic_fails(client: TestClient):
    token = get_token_for_user(client)
    create_res = client.post(
        "/chats",
        json={"title": "Chat avec messages"},
        headers={"Authorization": f"Bearer {token}"},
    )
    chat_id = create_res.json()["id"]

    with patch("main.run_chat_agent", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = "Réponse..."
        client.post(
            f"/chats/{chat_id}/messages",
            json={"content": "Bonjour"},
            headers={"Authorization": f"Bearer {token}"},
        )

    res = client.post(
        f"/chats/{chat_id}/press-review",
        json={"topic": "    "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 400
    assert "ne peut pas être vide" in res.json()["detail"]


def test_user_isolation_cannot_generate_press_review_on_other_users_chat(client: TestClient, session: Session):
    # User 1 creates chat
    token_user1 = get_token_for_user(client, "test@test.com", "test")
    create_res = client.post(
        "/chats",
        json={"title": "Chat secret de User 1"},
        headers={"Authorization": f"Bearer {token_user1}"},
    )
    chat1_id = create_res.json()["id"]

    # User 2 logs in
    create_second_user(session)
    token_user2 = get_token_for_user(client, "second@test.com", "test2")

    # User 2 tries to generate press review on User 1's chat -> 403 Forbidden
    res = client.post(
        f"/chats/{chat1_id}/press-review",
        json={"topic": "Tentative d'espionnage"},
        headers={"Authorization": f"Bearer {token_user2}"},
    )
    assert res.status_code == 403
    assert "Accès interdit" in res.json()["detail"]


def test_list_press_reviews_isolation(client: TestClient, session: Session):
    token_user1 = get_token_for_user(client, "test@test.com", "test")

    # 1. User 1 creates chat + message + press review
    create_res = client.post(
        "/chats",
        json={"title": "Discussion IA"},
        headers={"Authorization": f"Bearer {token_user1}"},
    )
    chat_id = create_res.json()["id"]

    with patch("main.run_chat_agent", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = "Contenu..."
        client.post(
            f"/chats/{chat_id}/messages",
            json={"content": "Question"},
            headers={"Authorization": f"Bearer {token_user1}"},
        )

    with patch("main.generate_press_review", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_PRESS_REVIEW_OUTPUT
        client.post(
            f"/chats/{chat_id}/press-review",
            json={"topic": "Tech"},
            headers={"Authorization": f"Bearer {token_user1}"},
        )

    # User 1 lists press reviews
    list_res1 = client.get("/press-reviews", headers={"Authorization": f"Bearer {token_user1}"})
    assert list_res1.status_code == 200
    items1 = list_res1.json()
    assert len(items1) >= 1
    assert any(i["chat_id"] == chat_id for i in items1)

    # 2. User 2 lists press reviews -> Must NOT see User 1's reviews!
    create_second_user(session)
    token_user2 = get_token_for_user(client, "second@test.com", "test2")

    list_res2 = client.get("/press-reviews", headers={"Authorization": f"Bearer {token_user2}"})
    assert list_res2.status_code == 200
    items2 = list_res2.json()
    assert len(items2) == 0

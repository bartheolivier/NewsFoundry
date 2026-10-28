import bcrypt
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlmodel import Session

from models import User


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


def test_create_chat(client: TestClient):
    token = get_token_for_user(client)
    response = client.post(
        "/chats",
        json={"title": "Ma première discussion"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Ma première discussion"
    assert data["messages"] == []
    assert "id" in data


def test_list_chats(client: TestClient):
    token = get_token_for_user(client)
    # Create two chats
    client.post("/chats", json={"title": "Chat 1"}, headers={"Authorization": f"Bearer {token}"})
    client.post("/chats", json={"title": "Chat 2"}, headers={"Authorization": f"Bearer {token}"})

    response = client.get("/chats", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    chats = response.json()
    assert len(chats) >= 2
    titles = [c["title"] for c in chats]
    assert "Chat 1" in titles
    assert "Chat 2" in titles


def test_get_chat_details(client: TestClient):
    token = get_token_for_user(client)
    create_res = client.post(
        "/chats",
        json={"title": "Chat détail"},
        headers={"Authorization": f"Bearer {token}"},
    )
    chat_id = create_res.json()["id"]

    response = client.get(f"/chats/{chat_id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["id"] == chat_id
    assert response.json()["title"] == "Chat détail"


def test_get_nonexistent_chat(client: TestClient):
    token = get_token_for_user(client)
    response = client.get("/chats/99999", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_user_isolation_cannot_access_other_users_chat(client: TestClient, session: Session):
    # 1. User 1 creates a chat
    token_user1 = get_token_for_user(client, "test@test.com", "test")
    create_res = client.post(
        "/chats",
        json={"title": "Chat privé de User 1"},
        headers={"Authorization": f"Bearer {token_user1}"},
    )
    chat1_id = create_res.json()["id"]

    # 2. User 2 is created and logs in
    create_second_user(session)
    token_user2 = get_token_for_user(client, "second@test.com", "test2")

    # 3. User 2 attempts to read User 1's chat -> MUST BE 403 FORBIDDEN
    forbidden_res = client.get(
        f"/chats/{chat1_id}",
        headers={"Authorization": f"Bearer {token_user2}"},
    )
    assert forbidden_res.status_code == 403
    assert "Accès interdit" in forbidden_res.json()["detail"]


def test_user_isolation_cannot_post_message_to_other_users_chat(client: TestClient, session: Session):
    # 1. User 1 creates a chat
    token_user1 = get_token_for_user(client, "test@test.com", "test")
    create_res = client.post(
        "/chats",
        json={"title": "Chat confidentiel"},
        headers={"Authorization": f"Bearer {token_user1}"},
    )
    chat1_id = create_res.json()["id"]

    # 2. User 2 is created and logs in
    create_second_user(session)
    token_user2 = get_token_for_user(client, "second@test.com", "test2")

    # 3. User 2 attempts to post a message into User 1's chat -> MUST BE 403 FORBIDDEN
    forbidden_post = client.post(
        f"/chats/{chat1_id}/messages",
        json={"content": "Tentative d'intrusion"},
        headers={"Authorization": f"Bearer {token_user2}"},
    )
    assert forbidden_post.status_code == 403
    assert "Accès interdit" in forbidden_post.json()["detail"]


def test_send_message_in_own_chat(client: TestClient):
    token = get_token_for_user(client)
    create_res = client.post(
        "/chats",
        json={"title": "Chat interactif"},
        headers={"Authorization": f"Bearer {token}"},
    )
    chat_id = create_res.json()["id"]

    # Send a message with mocked agent
    with patch("main.run_chat_agent", new_callable=AsyncMock) as mock_agent:
        mock_agent.return_value = ("Voici les actualités du jour.", [])
        msg_res = client.post(
            f"/chats/{chat_id}/messages",
            json={"content": "Quelles sont les nouvelles ?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert msg_res.status_code == 200
        msg_data = msg_res.json()
        assert msg_data["role"] == "assistant"
        assert len(msg_data["content"]) > 0

    # Verify history is persisted in database
    get_res = client.get(f"/chats/{chat_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 200
    messages = get_res.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Quelles sont les nouvelles ?"
    assert messages[1]["role"] == "assistant"


def test_send_message_handles_gemini_credits_depleted(client: TestClient):
    from pydantic_ai.exceptions import ModelHTTPError
    token = get_token_for_user(client)
    create_res = client.post(
        "/chats",
        json={"title": "Chat test quota"},
        headers={"Authorization": f"Bearer {token}"},
    )
    chat_id = create_res.json()["id"]

    depleted_err = ModelHTTPError(
        status_code=402,
        model_name="gemini-3.5-flash-lite",
        body={"error": {"code": 402, "message": "Your prepayment credits are depleted."}},
    )

    with patch("main.run_chat_agent", new_callable=AsyncMock) as mock_agent:
        mock_agent.side_effect = depleted_err
        msg_res = client.post(
            f"/chats/{chat_id}/messages",
            json={"content": "Quelles sont les nouvelles ?"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert msg_res.status_code == 402
        assert "crédits pour l'API Gemini" in msg_res.json()["detail"]


def test_delete_own_chat(client: TestClient):
    token = get_token_for_user(client)
    create_res = client.post(
        "/chats",
        json={"title": "Chat à supprimer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    chat_id = create_res.json()["id"]

    # Delete the chat
    delete_res = client.delete(f"/chats/{chat_id}", headers={"Authorization": f"Bearer {token}"})
    assert delete_res.status_code == 200
    assert delete_res.json()["id"] == chat_id

    # Verify it is gone
    get_res = client.get(f"/chats/{chat_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 404


def test_user_isolation_cannot_delete_other_users_chat(client: TestClient, session: Session):
    # 1. User 1 creates a chat
    token_user1 = get_token_for_user(client, "test@test.com", "test")
    create_res = client.post(
        "/chats",
        json={"title": "Chat précieux de User 1"},
        headers={"Authorization": f"Bearer {token_user1}"},
    )
    chat1_id = create_res.json()["id"]

    # 2. User 2 logs in
    create_second_user(session)
    token_user2 = get_token_for_user(client, "second@test.com", "test2")

    # 3. User 2 tries to delete User 1's chat -> MUST BE 403 FORBIDDEN
    delete_res = client.delete(
        f"/chats/{chat1_id}",
        headers={"Authorization": f"Bearer {token_user2}"},
    )
    assert delete_res.status_code == 403
    assert "Accès interdit" in delete_res.json()["detail"]

    # 4. Verify User 1 can still access their chat
    get_res = client.get(f"/chats/{chat1_id}", headers={"Authorization": f"Bearer {token_user1}"})
    assert get_res.status_code == 200


def test_update_chat_title_success(client: TestClient):
    token = get_token_for_user(client)
    create_res = client.post(
        "/chats",
        json={"title": "Ancien titre"},
        headers={"Authorization": f"Bearer {token}"},
    )
    chat_id = create_res.json()["id"]

    patch_res = client.patch(
        f"/chats/{chat_id}",
        json={"title": "Nouveau titre personnalisé"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Nouveau titre personnalisé"

    # Verify persisted
    get_res = client.get(f"/chats/{chat_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Nouveau titre personnalisé"


def test_update_chat_empty_title(client: TestClient):
    token = get_token_for_user(client)
    create_res = client.post(
        "/chats",
        json={"title": "Titre initial"},
        headers={"Authorization": f"Bearer {token}"},
    )
    chat_id = create_res.json()["id"]

    patch_res = client.patch(
        f"/chats/{chat_id}",
        json={"title": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 400
    assert "ne peut pas être vide" in patch_res.json()["detail"]


def test_user_isolation_cannot_update_other_users_chat(client: TestClient, session: Session):
    token_user1 = get_token_for_user(client, "test@test.com", "test")
    create_res = client.post(
        "/chats",
        json={"title": "Discussion privée de User 1"},
        headers={"Authorization": f"Bearer {token_user1}"},
    )
    chat1_id = create_res.json()["id"]

    create_second_user(session)
    token_user2 = get_token_for_user(client, "second@test.com", "test2")

    patch_res = client.patch(
        f"/chats/{chat1_id}",
        json={"title": "Titre piraté"},
        headers={"Authorization": f"Bearer {token_user2}"},
    )
    assert patch_res.status_code == 403
    assert "Accès interdit" in patch_res.json()["detail"]


def test_get_top_news_endpoint(client: TestClient):
    token = get_token_for_user(client)
    mock_articles = [
        {
            "title": "Une du jour : Accord sur l'énergie",
            "summary": "Résumé de l'accord énergétique...",
            "url": "https://example.com/energie",
            "publish_date": "2026-10-26",
        }
    ]
    with patch("main.get_top_news_api", new_callable=AsyncMock) as mock_top:
        mock_top.return_value = mock_articles
        # Unauthorized without token
        unauth_resp = client.get("/top-news")
        assert unauth_resp.status_code == 401

        # Authorized with token (default France)
        resp = client.get("/top-news", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert "Accord sur l'énergie" in data[0]["title"]
        assert "Résumé de l'accord" in data[0]["summary"]
        mock_top.assert_called_with(country="fr", language="fr")

        # Authorized with country US
        resp_us = client.get("/top-news?country=us", headers={"Authorization": f"Bearer {token}"})
        assert resp_us.status_code == 200
        mock_top.assert_called_with(country="us", language="en")




import bcrypt
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

    # Send a message
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

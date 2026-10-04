from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient
from llama_index.core.embeddings.mock_embed_model import MockEmbedding
from sqlmodel import Session

from agent import ChatDeps, get_article_content
from models import ArticleSummary, Chat, PressReviewOutput
from services.rag import build_rag_context, get_llama_embed_model


def get_token(client: TestClient) -> str:
    response = client.post("/login", json={"email": "test@test.com", "password": "test"})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.mark.anyio
async def test_get_article_content_records_url_in_chat_deps():
    """Vérifie que l'outil get_article_content consigne l'URL consultée dans ctx.deps."""
    deps = ChatDeps()
    fake_url = "https://lemonde.fr/article-test-123"

    with patch("agent.extract_article_content_api", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = {
            "title": "Article Test",
            "text": "Contenu complet de l'article pour le test.",
            "url": fake_url,
            "author": "Journaliste",
            "publish_date": "2026-10-04",
        }

        # Simuler un RunContext
        from unittest.mock import MagicMock
        ctx = MagicMock()
        ctx.deps = deps

        output = await get_article_content(ctx, fake_url)
        assert fake_url in deps.loaded_articles
        assert "Article Test" in output


@pytest.mark.anyio
async def test_build_rag_context_empty():
    """Vérifie que build_rag_context retourne None si la liste d'articles est vide."""
    res = await build_rag_context([], "transition énergétique")
    assert res is None


@pytest.mark.anyio
async def test_build_rag_context_success():
    """Vérifie l'indexation vectorielle LlamaIndex et la recherche sémantique."""
    sample_url = "https://example.com/article-ia"
    sample_article = {
        "title": "L'essor de l'Intelligence Artificielle en France",
        "text": (
            "L'intelligence artificielle transforme le journalisme d'investigation. "
            "Les rédactions intègrent de nouveaux outils d'aide à la synthèse et à l'analyse documentaire."
        ),
        "url": sample_url,
        "author": "Alice Dupont",
        "publish_date": "2026-10-01",
    }

    with patch("services.rag.extract_article_content_api", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = sample_article

        custom_embed = MockEmbedding(embed_dim=384)
        rag_context = await build_rag_context(
            loaded_urls=[sample_url],
            topic="journalisme et IA",
            similarity_top_k=2,
            custom_embed_model=custom_embed,
        )

        assert rag_context is not None
        assert "EXTRAITS DE DOCUMENTS ENRICHIS PAR RAG" in rag_context
        assert "L'essor de l'Intelligence Artificielle" in rag_context
        assert sample_url in rag_context


@pytest.mark.anyio
async def test_build_rag_context_error_handling():
    """Vérifie que les erreurs d'extraction sont gérées silencieusement et retournent None si aucun texte valide."""
    with patch("services.rag.extract_article_content_api", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = {"error": "Quota dépassé"}

        rag_context = await build_rag_context(
            loaded_urls=["https://example.com/failed"],
            topic="politique",
        )
        assert rag_context is None


def test_send_message_persists_loaded_articles(client: TestClient, session: Session):
    """Vérifie que lorsque l'agent consulte un article, son URL est mémorisée dans le modèle Chat en BDD."""
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/chats", json={"title": "Discussion RAG Test"}, headers=headers)
    chat_id = create_res.json()["id"]

    target_url = "https://actu.fr/voiture-electrique"

    # Simuler le retour de run_chat_agent avec l'URL chargée
    with patch("main.run_chat_agent", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = ("Voici le résumé de l'article.", [target_url])

        res = client.post(
            f"/chats/{chat_id}/messages",
            headers=headers,
            json={"content": "Lis cet article : https://actu.fr/voiture-electrique"},
        )
        assert res.status_code == 200

        # Vérifier via l'API GET /chats/{chat_id}
        get_res = client.get(f"/chats/{chat_id}", headers=headers)
        assert get_res.status_code == 200
        data = get_res.json()
        assert target_url in data.get("loaded_articles", [])


def test_press_review_generation_uses_rag_context(client: TestClient, session: Session):
    """Vérifie que la route de génération de revue de presse appelle build_rag_context avec les URLs chargées."""
    token = get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post("/chats", json={"title": "Discussion Mobilité"}, headers=headers)
    chat_id = create_res.json()["id"]

    target_url = "https://actu.fr/voiture-electrique"

    # Ajouter un message et l'URL chargée en BDD
    chat = session.get(Chat, chat_id)
    chat.messages = [
        {"role": "user", "content": "Que dit cet article ?", "timestamp": "2026-10-04T10:00:00Z"},
        {"role": "assistant", "content": "Il traite de l'électrique.", "timestamp": "2026-10-04T10:01:00Z"},
    ]
    chat.loaded_articles = [target_url]
    session.add(chat)
    session.commit()

    dummy_output = PressReviewOutput(
        title="REVUE DE PRESSE : VÉHICULES ÉLECTRIQUES",
        topic="Mobilité électrique",
        general_summary="Synthèse enrichie par RAG.",
        articles=[
            ArticleSummary(
                title="L'électrique en essor",
                source="Actu.fr",
                url=target_url,
                summary="Détails extraits via RAG.",
            )
        ],
        perspectives="Perspectives prometteuses.",
    )

    with patch("main.build_rag_context", new_callable=AsyncMock) as mock_rag, \
         patch("main.generate_press_review", new_callable=AsyncMock) as mock_review:

        mock_rag.return_value = "--- EXTRAITS RAG ---\nTexte de l'article"
        mock_review.return_value = dummy_output

        res = client.post(
            f"/chats/{chat_id}/press-review",
            headers=headers,
            json={"topic": "Mobilité électrique"},
        )

        assert res.status_code == 200
        mock_rag.assert_called_once_with(
            loaded_urls=[target_url],
            topic="Mobilité électrique",
        )
        mock_review.assert_called_once()
        _, kwargs = mock_review.call_args
        assert kwargs.get("rag_context") == "--- EXTRAITS RAG ---\nTexte de l'article"

        # Vérifier que le résultat est stocké dans le chat
        get_res = client.get(f"/chats/{chat_id}", headers=headers)
        chat_data = get_res.json()
        assert chat_data["press_review"] is not None
        assert chat_data["press_review"]["title"] == "REVUE DE PRESSE : VÉHICULES ÉLECTRIQUES"

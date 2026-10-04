import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from services.world_news import format_news_for_agent, search_news_api
from agent import get_agent, search_news
from pydantic_ai.models.test import TestModel


@pytest.mark.anyio
async def test_search_news_api_success():
    mock_response_data = {
        "count": 2,
        "news": [
            {
                "id": 101,
                "title": "Nouvelle avancée en IA",
                "summary": "Une grande découverte a été annoncée ce matin.",
                "url": "https://example.com/ia-news",
                "publish_date": "2026-10-04 09:00:00",
                "author": "Tech Journal",
                "source_country": "fr",
            },
            {
                "id": 102,
                "title": "Sommet pour le climat",
                "summary": "Les dirigeants mondiaux se réunissent à Paris.",
                "url": "https://example.com/climat",
                "publish_date": "2026-10-04 10:30:00",
                "author": "Le Monde",
                "source_country": "fr",
            },
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        result = await search_news_api("climat", api_key="dummy_key")

        assert result["count"] == 2
        assert len(result["news"]) == 2
        assert result["news"][0]["title"] == "Nouvelle avancée en IA"
        assert result["news"][0]["url"] == "https://example.com/ia-news"
        assert "error" not in result


@pytest.mark.anyio
async def test_search_news_api_empty():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"news": []}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        result = await search_news_api("sujet_introuvable", api_key="dummy_key")

        assert result["count"] == 0
        assert result["news"] == []
        formatted = format_news_for_agent(result)
        assert "Aucun article trouvé" in formatted


@pytest.mark.anyio
async def test_search_news_api_quota_exceeded():
    mock_resp = MagicMock()
    mock_resp.status_code = 402  # Payment Required / Quota Exceeded

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        result = await search_news_api("politique", api_key="dummy_key")

        assert "error" in result
        assert "Quota journalier" in result["error"]
        formatted = format_news_for_agent(result)
        assert "[Avertissement WorldNewsAPI]" in formatted


@pytest.mark.anyio
async def test_search_news_api_unauthorized():
    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        result = await search_news_api("tech", api_key="invalid_key")

        assert "error" in result
        assert "Erreur d'authentification" in result["error"]


@pytest.mark.anyio
async def test_search_news_api_rate_limit():
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        result = await search_news_api("bourse", api_key="dummy_key")

        assert "error" in result
        assert "Trop de requêtes" in result["error"]


@pytest.mark.anyio
async def test_search_news_api_timeout():
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Délai d'attente dépassé")
        result = await search_news_api("sport", api_key="dummy_key")

        assert "error" in result
        assert "Délai d'attente dépassé" in result["error"]


@pytest.mark.anyio
async def test_search_news_api_no_key():
    with patch.dict("os.environ", {}, clear=True):
        result = await search_news_api("france", api_key=None)
        assert "error" in result
        assert "Clé WORLD_NEWS_API_KEY non configurée" in result["error"]


def test_format_news_for_agent():
    sample_data = {
        "query": "technologie",
        "news": [
            {
                "title": "Lancement satellite",
                "publish_date": "2026-10-04",
                "author": "Agence Spatiale",
                "url": "https://example.com/space",
                "summary": "Fusée lancée avec succès.",
            }
        ],
    }
    formatted = format_news_for_agent(sample_data)
    assert "Titre : Lancement satellite" in formatted
    assert "Date : 2026-10-04" in formatted
    assert "Auteur/Source : Agence Spatiale" in formatted
    assert "Lien : https://example.com/space" in formatted
    assert "Fusée lancée avec succès" in formatted


@pytest.mark.anyio
async def test_agent_with_search_news_tool():
    # Use TestModel with call_tools to ensure search_news tool is registered and callable
    test_model = TestModel(call_tools=["search_news"])
    agent = get_agent(custom_model=test_model)

    # Mock search_news_api so the test does not call the real API
    mock_data = {
        "query": "actualités",
        "news": [
            {
                "title": "Vote du budget",
                "summary": "Le parlement examine le texte.",
                "url": "https://example.com/budget",
                "publish_date": "2026-10-04",
                "author": "Le Figaro",
            }
        ],
    }

    with patch("agent.search_news_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_data
        result = await agent.run("Quelles sont les actualités sur le budget ?")
        assert result is not None

from services.world_news import (
    extract_article_content_api,
    format_article_content_for_agent,
    get_top_news_api,
)


@pytest.mark.anyio
async def test_get_top_news_api_success():
    mock_data = {
        "top_news": [
            {
                "news": [
                    {
                        "title": "Une du jour : Accord international",
                        "summary": "Les pays ont signé l'accord.",
                        "url": "https://example.com/accord",
                        "publish_date": "2026-10-04",
                    }
                ]
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        articles = await get_top_news_api(country="fr", language="fr", api_key="dummy_key")
        assert len(articles) >= 1
        assert "Accord international" in articles[0]["title"]


@pytest.mark.anyio
async def test_extract_article_content_api_success():
    mock_data = {
        "title": "Article complet",
        "text": "Voici l'intégralité du texte de l'article avec tous ses détails...",
        "url": "https://example.com/article-full",
        "authors": ["Journaliste Spécialisé"],
        "publish_date": "2026-10-04",
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await extract_article_content_api("https://example.com/article-full", api_key="dummy_key")
        assert res["title"] == "Article complet"
        assert "Voici l'intégralité" in res["text"]


@pytest.mark.anyio
async def test_extract_article_content_api_quota_exceeded():
    mock_resp = MagicMock()
    mock_resp.status_code = 402

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        res = await extract_article_content_api("https://example.com/article-full", api_key="dummy_key")
        assert "error" in res
        assert "Quota journalier" in res["error"]


@pytest.mark.anyio
async def test_agent_with_extract_news_tool():
    test_model = TestModel(call_tools=["get_article_content"])
    agent = get_agent(custom_model=test_model)

    mock_extract_data = {
        "title": "Analyse géopolitique",
        "text": "Texte très complet analysant la situation en détail.",
        "url": "https://example.com/geopolitique",
        "publish_date": "2026-10-04",
    }

    with patch("agent.extract_article_content_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_extract_data
        result = await agent.run("Donne-moi les détails de l'article sur https://example.com/geopolitique")
        assert result is not None

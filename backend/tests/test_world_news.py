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
    format_news_for_agent,
    get_top_news_api,
    is_relevant_headline,
    search_news_api,
)


import services.world_news

def test_is_relevant_headline():
    # Podcasts, grilles radio et bulletins météo doivent être rejetés
    assert is_relevant_headline("Le 5/6 du lundi 26 octobre 2026", "Suivre Radio France sur Google...") is False
    assert is_relevant_headline("Podcast : Les grands dossiers", "Découvrez notre nouvel épisode...") is False
    assert is_relevant_headline("Météo du week-end en France", "Prévisions pour samedi et dimanche") is False
    assert is_relevant_headline("Le journal de 8h du 26 octobre", "Le point complet sur l'actualité") is False
    assert is_relevant_headline("Court", "Trop court") is False

    # Vraies actualités substantielles doivent être acceptées
    assert is_relevant_headline("Lula bat Flavio Bolsonaro et est réélu président du Brésil", "Le candidat de gauche a remporté l'élection...") is True
    assert is_relevant_headline("Mobilisation des lycéens : le gouvernement reçoit les organisations", "Des annonces sont attendues...") is True


@pytest.mark.anyio
async def test_get_top_news_api_filters_podcasts_and_keeps_substantive():
    services.world_news._top_news_cache = {"timestamp": 0, "data": []}
    mock_data = {
        "top_news": [
            {
                # Cluster 1 : Podcast / grille radio non pertinent
                "news": [
                    {
                        "title": "Le 5/6 du lundi 26 octobre 2026",
                        "summary": "Le 5/6 du lundi. Suivre Radio France sur Google...",
                        "url": "https://example.com/podcast-5-6",
                        "publish_date": "2026-10-26",
                    }
                ]
            },
            {
                # Cluster 2 : Vraie actualité majeure
                "news": [
                    {
                        "title": "Lula bat Flavio Bolsonaro et est réélu président du Brésil",
                        "summary": "Le candidat de gauche a été réélu président du Brésil.",
                        "url": "https://example.com/lula-election",
                        "publish_date": "2026-10-26",
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
        # Le premier cluster (podcast) doit avoir été ignoré au profit de l'actualité réelle
        assert len(articles) == 1
        assert "Lula bat Flavio Bolsonaro" in articles[0]["title"]


@pytest.mark.anyio
async def test_get_top_news_api_success():
    services.world_news._top_news_cache = {"timestamp": 0, "data": []}
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


def test_deduplicate_news_articles():
    from services.world_news import deduplicate_news_articles, canonical_url

    articles = [
        {"title": "Crise sociale. Reçus à Matignon...", "url": "https://a.com/1?utm_source=rss"},
        {"title": "En direct Social. Colère lycéenne : Sébastien Lecornu souhaite un débat sur Parcoursup à l'Assemblée", "url": "https://b.com/2"},
        # Doublon par titre (reprise de dépêche avec titre quasi-identique sur autre domaine)
        {"title": "Colère lycéenne : Sébastien Lecornu souhaite un débat sur Parcoursup à l'Assemblée", "url": "https://c.com/2bis"},
        {"title": "Maintien de l'ordre : Macron monte en première ligne", "url": "https://d.com/3"},
        # Doublon par URL canonique et par titre
        {"title": "Crise sociale. Reçus à Matignon...", "url": "https://e.com/1?ref=home"},
        {"title": "Élection au Brésil : victoire de Lula", "url": "https://f.com/4"},
    ]

    deduped = deduplicate_news_articles(articles, max_items=5)
    # Les doublons Matignon et Lecornu doivent être fusionnés
    assert len(deduped) == 4
    titles = [a["title"] for a in deduped]
    assert any("Matignon" in t for t in titles)
    assert any("Lecornu" in t for t in titles)
    assert any("Macron" in t for t in titles)
    assert any("Brésil" in t for t in titles)


@pytest.mark.anyio
async def test_get_top_news_api_country_us_and_cache_isolation():
    services.world_news._top_news_cache = {}

    us_mock_data = {
        "top_news": [
            {
                "news": [
                    {
                        "title": "US Federal Reserve cuts interest rates by 25 basis points",
                        "summary": "The central bank announced a new rate reduction today in Washington.",
                        "url": "https://example.com/fed-rates",
                        "publish_date": "2026-10-28",
                    }
                ]
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = us_mock_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        articles_us = await get_top_news_api(country="us", language="en", api_key="dummy_key")
        assert len(articles_us) == 1
        assert "Federal Reserve" in articles_us[0]["title"]
        assert mock_get.call_args[1]["params"] == {"source-country": "us", "language": "en"}

        # Vérifier que le cache est bien isolé pour "us_en"
        assert "us_en" in services.world_news._top_news_cache
        assert "fr_fr" not in services.world_news._top_news_cache

        # Appel ultérieur sur us utilise le cache (sans nouvel appel HTTP)
        cached_us = await get_top_news_api(country="us", language="en", api_key="dummy_key")
        assert len(cached_us) == 1
        assert mock_get.call_count == 1



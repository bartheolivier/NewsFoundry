import os
from typing import Any, Optional
import httpx

WORLD_NEWS_API_BASE = "https://api.worldnewsapi.com"


async def search_news_api(
    query: str,
    language: str = "fr",
    number: int = 5,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Appelle l'API WorldNewsAPI pour rechercher des articles d'actualité récents.

    Gère exhaustivement les codes HTTP (200, 401, 402 quota dépassé, 429 rate limit, 500)
    ainsi que les pannes réseau ou timeouts.
    """
    key = api_key or os.getenv("WORLD_NEWS_API_KEY")
    if not key:
        return {
            "error": "Clé WORLD_NEWS_API_KEY non configurée. Impossible de contacter l'API d'actualités.",
            "news": [],
            "count": 0,
            "query": query,
        }

    url = f"{WORLD_NEWS_API_BASE}/search-news"
    headers = {"x-api-key": key}
    params: dict[str, Any] = {
        "text": query,
        "number": max(1, min(number, 10)),
    }
    if language:
        params["language"] = language

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                raw_news = data.get("news", [])
                articles = []
                for item in raw_news:
                    summary = item.get("summary") or item.get("text", "")
                    if len(summary) > 400:
                        summary = summary[:400] + "..."
                    articles.append({
                        "id": item.get("id"),
                        "title": item.get("title", "Sans titre"),
                        "summary": summary,
                        "url": item.get("url", ""),
                        "publish_date": item.get("publish_date", ""),
                        "author": item.get("author") or "Rédaction",
                        "source_country": item.get("source_country", ""),
                    })
                return {
                    "count": len(articles),
                    "news": articles,
                    "query": query,
                }

            elif response.status_code == 401:
                return {
                    "error": "Erreur d'authentification WorldNewsAPI (clé API invalide ou révoquée).",
                    "news": [],
                    "count": 0,
                    "query": query,
                }
            elif response.status_code == 402:
                return {
                    "error": "Quota journalier WorldNewsAPI dépassé (50 requêtes/jour sur le plan gratuit).",
                    "news": [],
                    "count": 0,
                    "query": query,
                }
            elif response.status_code == 429:
                return {
                    "error": "Trop de requêtes envoyées à WorldNewsAPI (limite de débit atteinte).",
                    "news": [],
                    "count": 0,
                    "query": query,
                }
            else:
                return {
                    "error": f"Erreur du service WorldNewsAPI (code HTTP {response.status_code}).",
                    "news": [],
                    "count": 0,
                    "query": query,
                }

    except httpx.TimeoutException:
        return {
            "error": "Délai d'attente dépassé lors de la requête vers WorldNewsAPI.",
            "news": [],
            "count": 0,
            "query": query,
        }
    except httpx.RequestError as exc:
        return {
            "error": f"Erreur réseau lors de la communication avec WorldNewsAPI : {str(exc)}",
            "news": [],
            "count": 0,
            "query": query,
        }


def format_news_for_agent(result: dict[str, Any]) -> str:
    """Formate les résultats d'actualité sous forme de texte clair et structuré pour le LLM."""
    if "error" in result and result["error"]:
        return f"[Avertissement WorldNewsAPI] {result['error']}"

    articles = result.get("news", [])
    if not articles:
        return f"Aucun article trouvé pour la recherche : '{result.get('query', '')}'."

    output_lines = [
        f"Voici les {len(articles)} articles récents trouvés pour '{result.get('query', '')}' :",
        "",
    ]
    for idx, art in enumerate(articles, 1):
        output_lines.append(f"{idx}. Titre : {art['title']}")
        if art.get("publish_date"):
            output_lines.append(f"   Date : {art['publish_date']}")
        if art.get("author"):
            output_lines.append(f"   Auteur/Source : {art['author']}")
        if art.get("url"):
            output_lines.append(f"   Lien : {art['url']}")
        output_lines.append(f"   Résumé : {art['summary']}")
        output_lines.append("")

    return "\n".join(output_lines)

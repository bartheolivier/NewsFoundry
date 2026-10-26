import os
import re
import time
from typing import Any, List, Optional
import httpx

WORLD_NEWS_API_BASE = "https://api.worldnewsapi.com"

# In-memory cache for top news to avoid exhausting the 50 calls/day quota
_top_news_cache: dict[str, Any] = {"timestamp": 0, "data": []}
CACHE_TTL_SECONDS = 3600  # 1 hour cache

IRRELEVANT_HEADLINE_PATTERNS = [
    r"^le\s+\d+/\d+",                  # Ex: "Le 5/6 du lundi", "Le 6/9 du"
    r"^le\s+journal\s+de\s+\d+h",     # Ex: "Le journal de 8h"
    r"podcast",
    r"horoscope",
    r"météo\b",
    r"programme\s+tv",
    r"grille\s+des\s+programmes",
    r"ouverture\s+dans\s+un\s+nouvel\s+onglet",
    r"suivre\s+radio\s+france",
    r"^la\s+chronique\s+de",
    r"^le\s+billet\s+de",
    r"revue\s+de\s+presse\s+du",
]


def is_relevant_headline(title: str, summary: str = "") -> bool:
    """Filtre les annonces d'émissions, grilles de podcasts et bulletins sans contenu informatif réel."""
    if not title or len(title.strip()) < 15:
        return False
    combined = f"{title} {summary}".lower()
    for pattern in IRRELEVANT_HEADLINE_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return False
    return True


def canonical_url(url: str) -> str:
    """Nettoie une URL en supprimant les paramètres de tracking (?utm_...) et fragments pour comparaison."""
    if not url:
        return ""
    return url.split("?")[0].split("#")[0].rstrip("/")


def normalize_title_for_dedup(title: str) -> str:
    """Normalise un titre pour détecter les doublons de dépêches syndiquées."""
    if not title:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", title.lower())
    words = [w for w in cleaned.split() if len(w) > 2]
    return " ".join(words)


def deduplicate_news_articles(articles: List[dict[str, Any]], max_items: int = 5) -> List[dict[str, Any]]:
    """Élimine les doublons de dépêches d'agences (ex: dépêches AFP reprises sous plusieurs URLs ou titres quasi-identiques)."""
    unique_articles: List[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_titles: List[set[str]] = []

    for art in articles:
        url = canonical_url(art.get("url", ""))
        title = art.get("title", "").strip()
        norm_title = normalize_title_for_dedup(title)
        title_words = set(norm_title.split())

        # Doublon par URL canonique
        if url and url in seen_urls:
            continue

        # Doublon par titre (similarité de vocabulaire >= 70%)
        is_duplicate = False
        if title_words:
            for existing_words in seen_titles:
                overlap = len(title_words & existing_words)
                union = len(title_words | existing_words)
                similarity = overlap / union if union else 0
                if similarity >= 0.70:
                    is_duplicate = True
                    break

        if is_duplicate:
            continue

        if url:
            seen_urls.add(url)
        if title_words:
            seen_titles.append(title_words)
        unique_articles.append(art)

        if len(unique_articles) >= max_items:
            break

    return unique_articles


def get_world_news_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """Extrait la clé WorldNewsAPI depuis les arguments ou variables d'environnement."""
    return (
        api_key
        or os.getenv("WORLD_NEWS_API_KEY")
        or os.getenv("WORLDNEWS_API_KEY")
        or os.getenv("NEWS_API_KEY")
    )


async def get_top_news_api(
    country: str = "fr",
    language: str = "fr",
    api_key: Optional[str] = None,
) -> List[dict[str, Any]]:
    """Récupère les 3 actualités phares majeures du jour via la route /top-news de WorldNewsAPI.

    Met en cache les résultats 1h pour préserver le quota de requêtes.
    Filtre les grilles radio / podcasts pour ne retenir que de vrais événements informatifs.
    """
    global _top_news_cache
    now = time.time()
    if _top_news_cache["data"] and (now - _top_news_cache["timestamp"] < CACHE_TTL_SECONDS):
        return _top_news_cache["data"]

    key = get_world_news_api_key(api_key)
    if not key:
        return []

    url = f"{WORLD_NEWS_API_BASE}/top-news"
    headers = {"x-api-key": key}
    params = {"source-country": country, "language": language}

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                clusters = data.get("top_news", [])
                top_articles: List[dict[str, Any]] = []

                # Parcours des clusters en éliminant les programmes radio/podcasts
                for cluster in clusters:
                    cluster_news = cluster.get("news", [])
                    if cluster_news:
                        lead_article = cluster_news[0]
                        title = lead_article.get("title", "").strip()
                        raw_summary = lead_article.get("summary") or lead_article.get("text", "")

                        # Filtrage des non-actualités
                        if not is_relevant_headline(title, raw_summary):
                            continue

                        # Nettoyage des mentions parasites dans le résumé
                        summary = raw_summary
                        if "Suivre Radio France" in summary:
                            summary = summary.split("Suivre Radio France")[0].strip()
                        if len(summary) > 300:
                            summary = summary[:300].rstrip() + "..."

                        top_articles.append({
                            "title": title,
                            "summary": summary,
                            "url": lead_article.get("url", ""),
                            "publish_date": lead_article.get("publish_date", ""),
                        })

                        # Ne retenir que les 3 actualités majeures pour ne pas surcharger la vue
                        if len(top_articles) >= 3:
                            break

                # Fallback si le filtrage a été trop strict
                if not top_articles and clusters:
                    for cluster in clusters[:3]:
                        cluster_news = cluster.get("news", [])
                        if cluster_news:
                            lead_article = cluster_news[0]
                            top_articles.append({
                                "title": lead_article.get("title", "").strip(),
                                "summary": (lead_article.get("summary") or lead_article.get("text", ""))[:300],
                                "url": lead_article.get("url", ""),
                                "publish_date": lead_article.get("publish_date", ""),
                            })

                if top_articles:
                    _top_news_cache = {"timestamp": now, "data": top_articles}
                return top_articles
            return []
    except Exception:
        return []


async def search_news_api(
    query: str,
    language: str = "fr",
    number: int = 5,
    country: Optional[str] = None,
    earliest_publish_date: Optional[str] = None,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Appelle l'API WorldNewsAPI (/search-news) pour rechercher des articles d'actualité récents.

    Gère les filtres avancés (pays, dates) et les erreurs HTTP (401, 402, 429, timeouts).
    """
    key = get_world_news_api_key(api_key)
    if not key:
        return {
            "error": "Clé WORLD_NEWS_API_KEY non configurée. Impossible de contacter l'API d'actualités.",
            "news": [],
            "count": 0,
            "query": query,
        }

    url = f"{WORLD_NEWS_API_BASE}/search-news"
    headers = {"x-api-key": key}
    fetch_number = min(10, max(number * 2, 8))
    params: dict[str, Any] = {
        "text": query,
        "number": fetch_number,
    }
    if language:
        params["language"] = language
    if country:
        params["source-country"] = country
    if earliest_publish_date:
        params["earliest-publish-date"] = earliest_publish_date

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
                articles = deduplicate_news_articles(articles, max_items=number)
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


async def extract_article_content_api(
    url: str,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    """Appelle la route /extract-news de WorldNewsAPI pour extraire le contenu intégral d'un article."""
    key = get_world_news_api_key(api_key)
    if not key:
        return {
            "error": "Clé WORLD_NEWS_API_KEY non configurée.",
            "url": url,
        }

    api_endpoint = f"{WORLD_NEWS_API_BASE}/extract-news"
    headers = {"x-api-key": key}
    params = {"url": url}

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(api_endpoint, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                text = data.get("text", "")
                # Limit content to ~3000 chars to avoid blowing up context window
                if len(text) > 3000:
                    text = text[:3000] + "\n\n[... Texte tronqué pour respecter la taille de contexte ...]"
                return {
                    "title": data.get("title", ""),
                    "text": text,
                    "url": data.get("url", url),
                    "authors": data.get("authors", []),
                    "publish_date": data.get("publish_date", ""),
                }
            elif response.status_code == 402:
                return {"error": "Quota journalier WorldNewsAPI dépassé.", "url": url}
            else:
                return {"error": f"Impossible d'extraire l'article (code HTTP {response.status_code}).", "url": url}
    except Exception as exc:
        return {"error": f"Erreur lors de l'extraction de l'article : {str(exc)}", "url": url}


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


def format_article_content_for_agent(result: dict[str, Any]) -> str:
    """Formate le contenu intégral d'un article extrait pour l'agent."""
    if "error" in result and result["error"]:
        return f"[Erreur lors de l'extraction de l'article] {result['error']}"

    title = result.get("title", "Article")
    url = result.get("url", "")
    publish_date = result.get("publish_date", "")
    text = result.get("text", "")

    return (
        f"### Contenu extrait de l'article : {title}\n"
        f"Source : {url}\n"
        f"Date de publication : {publish_date}\n\n"
        f"Contenu intégral :\n{text}\n"
    )

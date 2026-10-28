import os
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.test import TestModel

from services.world_news import (
    canonical_url,
    deduplicate_news_articles,
    extract_article_content_api,
    format_article_content_for_agent,
    format_news_for_agent,
    normalize_title_for_dedup,
    search_news_api,
)

# NewsFoundry system prompt for journalistic assistance
DEFAULT_SYSTEM_PROMPT = """Tu es l'assistant IA de NewsFoundry, une plateforme SaaS dédiée aux journalistes, pigistes et professionnels des médias.
Ton rôle est d'aider les journalistes à explorer l'actualité, synthétiser des événements récents, répondre à leurs questions d'investigation et préparer des revues de presse.

Règles impératives :
1. Recherche d'actualités en direct : Tu as accès à l'outil `search_news`. Utilise-le SYSTÉMATIQUEMENT dès que la question de l'utilisateur porte sur des événements récents, des actualités du jour, des déclarations de personnalités, des marchés financiers, ou des thématiques nécessitant des faits vérifiés et à jour.
CONSIGNE DE RECHERCHE STRICTE POUR L'OUTIL `search_news` :
- L'API WorldNewsAPI effectue une recherche stricte par mots-clés.
- Ta `query` DOIT IMPÉRATIVEMENT être courte : 1 à 3 mots-clés maximum (ex: 'bourse Asie', 'CAC 40', 'Nikkei', 'Wall Street', 'taux OAT').
- Ne mets JAMAIS de longues phrases, ni d'accumulation de synonymes ou de listes de pays (ex: STRICTEMENT INTERDIT : 'marches asiatiques bourses bourse de tokyo shanghai hong kong actualite').
- CIBLAGE GÉOGRAPHIQUE ET LINGUISTIQUE DES SOURCES (RÈGLE ESSENTIELLE) :
  * Si la requête concerne l'actualité des États-Unis / USA (ou si l'utilisateur soumet un titre ou une question en anglais / sources US) : tu DOIS IMPÉRATIVEMENT spécifier `language='en'` et `country='us'` dans `search_news` afin d'interroger directement les grands médias américains (Associated Press, New York Times, Washington Post, CNN, NBC, etc.) et NON des médias français.
  * Si la requête concerne le Royaume-Uni (sources UK) : spécifie `language='en'` et `country='gb'`.
  * Si la requête concerne l'Allemagne (sources DE) : spécifie `language='de'` et `country='de'`.
  * Si la requête concerne la France : spécifie `language='fr'` et `country='fr'`.
  * RÈGLE DE RÉDACTION : Rédige TOUJOURS ton analyse en français pour le journaliste (sauf demande contraire explicite), tout en traduisant et en citant fidèlement les articles des médias originaux du pays ciblé.
2. Lecture approfondie d'articles : Tu as accès à l'outil `get_article_content`. Utilise-le dès que l'utilisateur demande des précisions, des citations exactes ou une analyse détaillée d'un article spécifique.
3. Démarche journalistique : Adopte un ton journalistique, professionnel, objectif, clair et structuré.
4. Formattage Markdown : Structure tes réponses avec soin en utilisant du Markdown (titres, listes à puces, éléments clés en gras).
5. CITATION OBLIGATOIRE DES SOURCES AVEC LIENS CLIQUABLES :
Lorsque tu utilises des informations issues de tes outils, tu DOIS TOUJOURS citer tes sources avec leurs liens Markdown cliquables vers les articles originaux (syntaxe obligatoire : `[Nom du média - Titre](url)`).
À la fin de ta réponse, ajoute SYSTÉMATIQUEMENT une section distincte intitulée :
### 📰 Sources consultées
Listant sous forme de puces chaque article trouvé :
- [Titre de l'article](url) — Source / Auteur (Date)
Il est FORMELLEMENT INTERDIT de mentionner un média sans insérer son lien URL Markdown complet.
DÉDUPLICATION OBLIGATOIRE : Ne liste JAMAIS deux fois le même article ou la même dépêche dans la section 'Sources consultées' (chaque puce doit correspondre à une actualité unique et distincte).
6. TRANSPARENCE ET VÉRACITÉ (RÈGLE ABSOLUE) :
Si `search_news` ne renvoie aucun article ou si une erreur/quota survient :
- Tu DOIS déclarer explicitement et immédiatement à l'utilisateur : "Aucun article récent n'a été trouvé dans le flux de dépêches en direct pour cette recherche." (ou signaler le dépassement de quota le cas échéant).
- Il t'est FORMELLEMENT INTERDIT d'inventer des citations de presse fictives ou d'affirmer que des médias (comme Reuters, Bloomberg, Les Échos, etc.) disent ceci ou cela sans avoir l'article réel issu de `search_news`.
- Tu peux fournir une mise en perspective générale issue de tes connaissances de fond, mais en précisant explicitement qu'il s'agit d'une analyse générale et non d'articles de presse en direct.
"""


@dataclass
class ChatDeps:
    """Dépendances injectées dans les exécutions de l'agent de chat pour suivre l'état de la session."""
    loaded_articles: List[str] = field(default_factory=list)
    # Métadonnées des articles réellement obtenus pendant le tour courant (titre, url, source, date)
    turn_sources: List[dict[str, str]] = field(default_factory=list)


SOURCES_HEADER = "### 📰 Sources consultées"

CITATION_REMINDER = (
    "\n[RAPPEL OBLIGATOIRE] Appuie ta réponse sur ces articles, cite-les dans le texte "
    "avec des liens Markdown [Titre](url) et termine par la section '" + SOURCES_HEADER + "'."
)


def _record_source(deps: Optional[ChatDeps], url: str, title: str = "", source: str = "", date: str = "") -> None:
    """Mémorise une source consultée pendant le tour (dédupliquée par URL canonique et titre)."""
    if deps is None or not url:
        return
    canon_url = canonical_url(url)
    if url not in deps.loaded_articles and canon_url not in deps.loaded_articles:
        deps.loaded_articles.append(url)

    norm_title = normalize_title_for_dedup(title)
    title_words = set(norm_title.split())

    for s in deps.turn_sources:
        if canonical_url(s.get("url", "")) == canon_url:
            return
        s_words = set(normalize_title_for_dedup(s.get("title", "")).split())
        if title_words and s_words:
            overlap = len(title_words & s_words)
            union = len(title_words | s_words)
            if union and (overlap / union) >= 0.70:
                return

    deps.turn_sources.append({
        "url": url,
        "title": (title or url).strip(),
        "source": (source or "").strip(),
        "date": (date or "")[:10],
    })


def _format_sources_section(sources: List[dict[str, str]]) -> str:
    lines = [SOURCES_HEADER]
    for s in sources:
        title = s["title"].replace("[", "(").replace("]", ")")
        meta = " ".join(p for p in [s.get("source", ""), f"({s['date']})" if s.get("date") else ""] if p)
        lines.append(f"- [{title}]({s['url']})" + (f" — {meta}" if meta else ""))
    return "\n".join(lines)


def deduplicate_sources_section(text: str) -> str:
    """Nettoie la section 'Sources consultées' pour éliminer les doublons de puces (URL ou titre)."""
    pattern = r"(###?\s*📰?\s*Sources consultées)"
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return text

    header_start = match.start()
    header_end = match.end()
    prefix = text[:header_start]
    header = text[header_start:header_end]
    sources_body = text[header_end:]

    lines = sources_body.split("\n")
    cleaned_lines: List[str] = []
    seen_urls: set[str] = set()
    seen_titles: List[set[str]] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("- ", "* ", "• ")):
            link_match = re.search(r"\[(.*?)\]\((.*?)\)", stripped)
            if link_match:
                title, url = link_match.groups()
                canon = canonical_url(url)
                norm_title = normalize_title_for_dedup(title)
                title_words = set(norm_title.split())

                if canon and canon in seen_urls:
                    continue

                is_duplicate = False
                if title_words:
                    for existing_words in seen_titles:
                        overlap = len(title_words & existing_words)
                        union = len(title_words | existing_words)
                        if union and (overlap / union) >= 0.70:
                            is_duplicate = True
                            break

                if is_duplicate:
                    continue

                if canon:
                    seen_urls.add(canon)
                if title_words:
                    seen_titles.append(title_words)
            else:
                norm_line = normalize_title_for_dedup(stripped)
                line_words = set(norm_line.split())
                is_duplicate = False
                if line_words:
                    for existing_words in seen_titles:
                        overlap = len(line_words & existing_words)
                        union = len(line_words | existing_words)
                        if union and (overlap / union) >= 0.70:
                            is_duplicate = True
                            break
                if is_duplicate:
                    continue
                if line_words:
                    seen_titles.append(line_words)

        cleaned_lines.append(line)

    return prefix + header + "\n".join(cleaned_lines)


def ensure_sources_section(text: str, sources: List[dict[str, str]]) -> str:
    """Garantit la présence d'une section de sources cliquables lorsque des articles ont été consultés.

    Si le modèle a omis la section (ou n'a inséré aucun des liens), elle est générée à partir
    des articles réellement renvoyés par les outils pendant le tour.
    Nettoie également les éventuels doublons dans la section finale.
    """
    if not sources:
        return deduplicate_sources_section(text)
    has_header = "Sources consultées" in text
    has_any_link = any(canonical_url(s["url"]) in text or s["url"] in text for s in sources)
    if has_header and has_any_link:
        return deduplicate_sources_section(text)
    return deduplicate_sources_section(text.rstrip() + "\n\n" + _format_sources_section(sources))


STOPWORDS = {
    "actualite", "actualites", "actualité", "actualités", "article", "articles",
    "presse", "nouvelles", "news", "dernieres", "dernières", "recentes", "récentes",
    "de", "des", "du", "la", "le", "les", "en", "un", "une", "sur", "dans", "pour", "par",
    "et", "ou", "que", "qui", "quoi", "dont", "avec", "sans", "sous", "bourses",
}


def _simplify_query(q: str) -> str:
    tokens = [w for w in q.lower().split() if w not in STOPWORDS]
    seen = set()
    unique_tokens = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            unique_tokens.append(t)
    return " ".join(unique_tokens[:3])


async def search_news(
    ctx: RunContext[Optional[ChatDeps]],
    query: str,
    language: Optional[str] = None,
    country: Optional[str] = None,
) -> str:
    """Recherche des articles et dépêches d'actualités récentes sur un sujet ou un mot-clé via WorldNewsAPI.

    IMPORTANT : WorldNewsAPI est un moteur par mots-clés stricts. La query doit être très concise
    (1 à 3 mots-clés maximum, ex: 'Dolores Huerta', 'Wall Street', 'Fed rates', 'CAC 40'). Ne pas mettre de phrases.

    CIBLAGE DES SOURCES INTERNATIONALES :
    - Pour les États-Unis (ou sujet/titre en anglais américain) : spécifier language='en' et country='us'.
    - Pour le Royaume-Uni : spécifier language='en' et country='gb'.
    - Pour l'Allemagne : spécifier language='de' et country='de'.
    - Pour la France : spécifier language='fr' et country='fr'.

    Args:
        query: Le mot-clé ou la thématique d'actualité recherchée (1 à 3 mots maximum).
        language: Code langue des articles ('fr', 'en', 'de', etc.).
        country: Code pays de la source ('fr', 'us', 'gb', 'de', etc.).
    """
    target_language = language
    target_country = country

    # Détection automatique de secours si l'agent n'a pas spécifié la langue ou le pays
    if not target_language:
        q_lower = query.lower()
        uk_patterns = [r"\b(uk|britain|british|britannique|london|parliament|starmer|sunak)\b"]
        de_patterns = [r"\b(germany|german|allemagne|allemand|scholz|bundestag|wirtschaft)\b"]
        us_patterns = [
            r"\b(us|usa|america|american|américain|américaine|états-unis|washington|biden|trump|harris|fed)\b",
            r"\b(dies\s+at|killed|court|judge|strike|cuts|rates|stocks|election|labor|activist|senate|congress|white\s+house)\b",
        ]

        if any(re.search(p, q_lower) for p in uk_patterns):
            target_language = "en"
            target_country = target_country or "gb"
        elif any(re.search(p, q_lower) for p in de_patterns):
            target_language = "de"
            target_country = target_country or "de"
        elif any(re.search(p, q_lower) for p in us_patterns):
            target_language = "en"
            target_country = target_country or "us"
        else:
            target_language = "fr"
            target_country = target_country or "fr"

    res = await search_news_api(query=query, language=target_language, country=target_country, number=5)
    # If no news found and query was verbose, automatically retry with simplified keywords
    if not res.get("news") and not res.get("error"):
        simplified = _simplify_query(query)
        if simplified and simplified != query.lower():
            res = await search_news_api(query=simplified, language=target_language, country=target_country, number=5)

    # Si aucun résultat avec un filtre pays restrictif, tenter un fallback sur la langue seule (ex: sources anglophones)
    if not res.get("news") and not res.get("error") and target_country:
        res = await search_news_api(query=query, language=target_language, country=None, number=5)

    for item in res.get("news", []):
        _record_source(
            ctx.deps,
            url=item.get("url", ""),
            title=item.get("title", ""),
            source=item.get("author", ""),
            date=item.get("publish_date", ""),
        )
    formatted = format_news_for_agent(res)
    if res.get("news"):
        formatted += CITATION_REMINDER
    return formatted


async def get_article_content(
    ctx: RunContext[Optional[ChatDeps]],
    url: str,
) -> str:
    """Extrait et lit le texte intégral d'un article d'actualité à partir de son URL via WorldNewsAPI.

    À utiliser lorsque l'utilisateur demande des détails supplémentaires, des citations directes,
    ou une analyse approfondie d'un article découvert lors d'une recherche.

    Args:
        url: L'URL exacte de l'article de presse à lire et analyser.
    """
    res = await extract_article_content_api(url=url)
    if ctx.deps is not None and url not in ctx.deps.loaded_articles:
        ctx.deps.loaded_articles.append(url)
    if not res.get("error"):
        _record_source(
            ctx.deps,
            url=res.get("url") or url,
            title=res.get("title", ""),
            source=", ".join(res.get("authors") or []),
            date=res.get("publish_date", ""),
        )
        return format_article_content_for_agent(res) + CITATION_REMINDER
    return format_article_content_for_agent(res)


def get_agent(
    custom_model: Optional[Any] = None,
    system_prompt_override: Optional[str] = None,
) -> Agent:
    """Instantiates and returns the PydanticAI Agent configured for the environment."""
    tools = [search_news, get_article_content]
    prompt = system_prompt_override or DEFAULT_SYSTEM_PROMPT

    if custom_model is not None:
        return Agent(custom_model, system_prompt=prompt, tools=tools, deps_type=Optional[ChatDeps])

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

    if gemini_key:
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider
        provider = GoogleProvider(api_key=gemini_key)
        model = GoogleModel(model_name, provider=provider)
        return Agent(model, system_prompt=prompt, tools=tools, deps_type=Optional[ChatDeps])
    elif openai_key:
        return Agent(
            f"openai:{os.getenv('LLM_MODEL', 'gpt-4o-mini')}",
            system_prompt=prompt,
            tools=tools,
            deps_type=Optional[ChatDeps],
        )
    else:
        # Fallback to TestModel when no API key is configured yet
        return Agent(
            TestModel(
                custom_output_text="Bonjour ! Je suis l'assistant IA de NewsFoundry. Pour activer mes réponses en temps réel, veuillez renseigner votre clé `GEMINI_API_KEY` dans le fichier `.env` ou sur Railway."
            ),
            system_prompt=prompt,
            tools=tools,
            deps_type=Optional[ChatDeps],
        )


def build_model_messages(history: List[dict[str, Any]]) -> List[ModelMessage]:
    """Converts serialized chat messages into PydanticAI ModelMessage instances."""
    model_messages: List[ModelMessage] = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            model_messages.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        elif role == "assistant":
            model_messages.append(ModelResponse(parts=[TextPart(content=content)]))
    return model_messages


async def run_chat_agent(
    history: List[dict[str, Any]],
    user_prompt: str,
    agent_override: Optional[Agent] = None,
    system_prompt_override: Optional[str] = None,
    deps: Optional[ChatDeps] = None,
) -> tuple[str, List[str]]:
    """Executes the agent run given prior conversation history and current user prompt.

    Returns a tuple (assistant_text, newly_loaded_urls).
    """
    agent = agent_override or get_agent(system_prompt_override=system_prompt_override)
    message_history = build_model_messages(history)
    actual_deps = deps if deps is not None else ChatDeps()
    result = await agent.run(user_prompt, message_history=message_history, deps=actual_deps)
    text = ensure_sources_section(str(result.output), actual_deps.turn_sources)
    return text, actual_deps.loaded_articles


# ---------------------------------------------------------
# Agent spécialisé pour la Revue de Presse (Étape 7)
# ---------------------------------------------------------

PRESS_REVIEW_SYSTEM_PROMPT = """Tu es le rédacteur en chef expert de NewsFoundry, spécialisé dans la rédaction de revues de presse journalistiques de référence.
Ton rôle est d'analyser l'intégralité des recherches, dépêches, articles et échanges issus d'une discussion journalistique pour composer une revue de presse structurée, claire, neutre et percutante sur le thème demandé.

Règles impératives de rédaction :
1. Titre : Propose un grand titre en majuscules (ex: 'REVUE DE PRESSE : TRANSITION ÉNERGÉTIQUE ET MOBILITÉ ÉLECTRIQUE').
2. Thème : Rappelle le sujet ciblé.
3. Synthèse générale : Développe une synthèse d'ensemble soignée (2 à 4 paragraphes) articulant les faits essentiels, chiffres marquants et tendances de fond.
4. Synthèse des articles : Identifie tous les articles clés et sources cités dans la discussion se rapportant au thème. Pour chacun, précise le titre, la source, le lien URL d'origine si disponible, et un résumé percutant de son apport.
5. Perspectives : Conclus avec les enjeux d'avenir, les prochaines échéances ou les questions en suspens.
6. Structured Output : Respecte rigoureusement le schéma JSON imposé.
"""


def get_press_review_agent(
    custom_model: Optional[Any] = None,
) -> Agent:
    """Instancie un agent PydanticAI spécialisé dans la synthèse de revue de presse avec Structured Output."""
    from models import PressReviewOutput

    prompt = PRESS_REVIEW_SYSTEM_PROMPT

    if custom_model is not None:
        return Agent(custom_model, output_type=PressReviewOutput, system_prompt=prompt)

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

    if gemini_key:
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        provider = GoogleProvider(api_key=gemini_key)
        model = GoogleModel(model_name, provider=provider)
        return Agent(model, output_type=PressReviewOutput, system_prompt=prompt)
    elif openai_key:
        return Agent(
            f"openai:{os.getenv('LLM_MODEL', 'gpt-4o-mini')}",
            output_type=PressReviewOutput,
            system_prompt=prompt,
        )
    else:
        from models import ArticleSummary

        dummy_review = PressReviewOutput(
            title="REVUE DE PRESSE : ACTUALITÉS DU JOUR",
            topic="Actualités",
            general_summary="Synthèse par défaut en mode test.",
            articles=[
                ArticleSummary(
                    title="Exemple de dépêche",
                    source="NewsFoundry",
                    url="https://example.com/info",
                    summary="Résumé de l'article.",
                )
            ],
            perspectives="Perspectives à observer.",
        )
        return Agent(
            TestModel(custom_output_args=dummy_review.model_dump()),
            output_type=PressReviewOutput,
            system_prompt=prompt,
        )


async def generate_press_review(
    chat_messages: List[dict[str, Any]],
    topic: str,
    system_prompt: Optional[str] = None,
    agent_override: Optional[Agent] = None,
    rag_context: Optional[str] = None,
):
    """Génère une revue de presse structurée sur le sujet donné à partir de l'historique de discussion et du contexte RAG."""
    agent = agent_override or get_press_review_agent()

    history_lines: List[str] = []
    if system_prompt:
        history_lines.append(f"--- Contexte initial de la session ---\n{system_prompt}\n")

    history_lines.append("--- Échanges de la discussion ---")
    for msg in chat_messages:
        role_label = "Journaliste" if msg.get("role") == "user" else "Assistant IA"
        content = msg.get("content", "")
        history_lines.append(f"{role_label} :\n{content}\n")

    conversation_context = "\n".join(history_lines)

    rag_section = ""
    if rag_context:
        rag_section = f"\n{rag_context}\n"

    user_prompt = f"""Voici l'ensemble de la discussion de travail et des recherches effectuées avec le journaliste :

{conversation_context}
{rag_section}
-------------------------
SUJET CIBLÉ DE LA REVUE DE PRESSE : {topic}
-------------------------
En te basant rigoureusement sur les faits, articles et données partagés dans cette discussion (ainsi que les extraits documentaires fournis ci-dessus), produis la revue de presse structurée demandée sur le sujet '{topic}'.
"""

    result = await agent.run(user_prompt)
    return result.output


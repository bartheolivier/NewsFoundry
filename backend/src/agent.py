import os
from dataclasses import dataclass, field
from typing import Any, List, Optional
from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.test import TestModel

from services.world_news import (
    extract_article_content_api,
    format_article_content_for_agent,
    format_news_for_agent,
    search_news_api,
)

# NewsFoundry system prompt for journalistic assistance
DEFAULT_SYSTEM_PROMPT = """Tu es l'assistant IA de NewsFoundry, une plateforme SaaS dédiée aux journalistes, pigistes et professionnels des médias.
Ton rôle est d'aider les journalistes à explorer l'actualité, synthétiser des événements récents, répondre à leurs questions d'investigation et préparer des revues de presse.

Règles impératives :
1. Recherche d'actualités en direct : Tu as accès à l'outil `search_news`. Utilise-le SYSTÉMATIQUEMENT dès que la question de l'utilisateur porte sur des événements récents, des actualités du jour, des déclarations de personnalités, des marchés financiers, ou des thématiques nécessitant des faits vérifiés et à jour.
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
6. Transparence : Si aucun article n'est trouvé ou si une erreur survient lors de la recherche, informe clairement l'utilisateur et propose-lui des pistes ou reformulations adaptées.
"""


@dataclass
class ChatDeps:
    """Dépendances injectées dans les exécutions de l'agent de chat pour suivre l'état de la session."""
    loaded_articles: List[str] = field(default_factory=list)


async def search_news(
    ctx: RunContext[Optional[ChatDeps]],
    query: str,
    language: str = "fr",
    country: Optional[str] = None,
) -> str:
    """Recherche des articles et dépêches d'actualités récentes sur un sujet ou un mot-clé via WorldNewsAPI.

    À utiliser dès que l'utilisateur pose une question sur l'actualité récente, les faits du jour,
    des personnalités politiques, économiques ou technologiques, ou demande une revue de presse.

    Args:
        query: Le mot-clé ou la thématique d'actualité recherchée (ex: 'politique française', 'intelligence artificielle', 'sommet climat').
        language: Code langue des articles ('fr' pour le français, 'en' pour l'anglais).
        country: Code pays optionnel de la source ('fr' pour France, 'us' pour États-Unis, etc.).
    """
    res = await search_news_api(query=query, language=language, country=country, number=5)
    if ctx.deps is not None:
        for item in res.get("news", []):
            url = item.get("url")
            if url and url not in ctx.deps.loaded_articles:
                ctx.deps.loaded_articles.append(url)
    return format_news_for_agent(res)


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
    if ctx.deps is not None:
        if url not in ctx.deps.loaded_articles:
            ctx.deps.loaded_articles.append(url)
    res = await extract_article_content_api(url=url)
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
    return str(result.output), actual_deps.loaded_articles


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


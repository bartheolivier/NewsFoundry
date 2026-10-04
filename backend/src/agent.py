import os
from typing import Any, List, Optional
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.test import TestModel

from services.world_news import format_news_for_agent, search_news_api

# NewsFoundry system prompt for journalistic assistance
SYSTEM_PROMPT = """Tu es l'assistant IA de NewsFoundry, une plateforme SaaS dédiée aux journalistes, pigistes et professionnels des médias.
Ton rôle est d'aider les journalistes à explorer l'actualité, synthétiser des événements récents, répondre à leurs questions d'investigation et préparer des revues de presse.

Règles impératives :
1. Recherche d'actualités en direct : Tu as accès à l'outil `search_news`. Utilise-le SYSTÉMATIQUEMENT dès que la question de l'utilisateur porte sur des événements récents, des actualités du jour, des déclarations de personnalités ou des thématiques nécessitant des faits vérifiés et à jour.
2. Démarche journalistique : Adopte un ton journalistique, professionnel, objectif, clair et structuré.
3. Formattage Markdown : Structure tes réponses avec soin en utilisant du Markdown (titres, listes à puces, éléments clés en gras).
4. CITATION DES SOURCES : Lorsque tu utilises des informations issues de l'outil `search_news`, mentionne systématiquement la source/le média et inclus les liens markdown vers les articles originaux (ex: [Titre de l'article](url)).
5. Transparence : Si aucun article n'est trouvé ou si une erreur survient lors de la recherche, informe clairement l'utilisateur et propose-lui des pistes ou reformulations adaptées.
"""


async def search_news(query: str, language: str = "fr") -> str:
    """Recherche des articles et dépêches d'actualités récentes sur un sujet ou un mot-clé via WorldNewsAPI.

    À utiliser dès que l'utilisateur pose une question sur l'actualité récente, les faits du jour,
    des personnalités politiques, économiques ou technologiques, ou demande une revue de presse.

    Args:
        query: Le mot-clé ou la thématique d'actualité recherchée (ex: 'politique française', 'intelligence artificielle', 'sommet climat').
        language: Code langue des articles (par défaut 'fr' pour le français, ou 'en' pour l'anglais).
    """
    res = await search_news_api(query=query, language=language, number=5)
    return format_news_for_agent(res)


def get_agent(custom_model: Optional[Any] = None) -> Agent:
    """Instantiates and returns the PydanticAI Agent configured for the environment."""
    tools = [search_news]

    if custom_model is not None:
        return Agent(custom_model, system_prompt=SYSTEM_PROMPT, tools=tools)

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

    if gemini_key:
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider
        provider = GoogleProvider(api_key=gemini_key)
        model = GoogleModel(model_name, provider=provider)
        return Agent(model, system_prompt=SYSTEM_PROMPT, tools=tools)
    elif openai_key:
        return Agent(
            f"openai:{os.getenv('LLM_MODEL', 'gpt-4o-mini')}",
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
        )
    else:
        # Fallback to TestModel when no API key is configured yet
        return Agent(
            TestModel(
                custom_output_text="Bonjour ! Je suis l'assistant IA de NewsFoundry. Pour activer mes réponses en temps réel, veuillez renseigner votre clé `GEMINI_API_KEY` dans le fichier `.env` ou sur Railway."
            ),
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
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
) -> str:
    """Executes the agent run given prior conversation history and current user prompt."""
    agent = agent_override or get_agent()
    message_history = build_model_messages(history)
    result = await agent.run(user_prompt, message_history=message_history)
    return str(result.output)

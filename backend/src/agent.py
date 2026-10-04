import os
from typing import Any, List, Optional
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.test import TestModel

# NewsFoundry system prompt for journalistic assistance
SYSTEM_PROMPT = """Tu es l'assistant IA de NewsFoundry, une plateforme SaaS dédiée aux journalistes, pigistes et professionnels des médias.
Ton rôle est d'aider les journalistes à explorer l'actualité, synthétiser des événements, répondre à leurs questions d'investigation et préparer des revues de presse.
Consignes fondamentales :
1. Adopte un ton journalistique, professionnel, objectif, clair et structuré.
2. Formate tes réponses avec soin en utilisant du Markdown (titres, listes à puces, éléments clés en gras).
3. Sois concis et direct, tout en restant précis et factuel.
4. Si l'utilisateur te demande de l'aide sur un sujet, synthétise les points majeurs et propose des axes d'approfondissement.
"""


def get_agent(custom_model: Optional[Any] = None) -> Agent:
    """Instantiates and returns the PydanticAI Agent configured for the environment."""
    if custom_model is not None:
        return Agent(custom_model, system_prompt=SYSTEM_PROMPT)

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("LLM_MODEL", "gemini-2.5-flash-lite")

    if gemini_key:
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider
        provider = GoogleProvider(api_key=gemini_key)
        model = GoogleModel(model_name, provider=provider)
        return Agent(model, system_prompt=SYSTEM_PROMPT)
    elif openai_key:
        return Agent(f"openai:{os.getenv('LLM_MODEL', 'gpt-4o-mini')}", system_prompt=SYSTEM_PROMPT)
    else:
        # Fallback to TestModel when no API key is configured yet
        return Agent(
            TestModel(
                custom_output_text="Bonjour ! Je suis l'assistant IA de NewsFoundry. Pour activer mes réponses en temps réel, veuillez renseigner votre clé `GEMINI_API_KEY` dans le fichier `.env` ou sur Railway."
            ),
            system_prompt=SYSTEM_PROMPT,
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

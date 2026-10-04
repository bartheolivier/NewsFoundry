import logging
import os
from typing import Any, List, Optional
from llama_index.core import Document, VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from services.world_news import extract_article_content_api

logger = logging.getLogger(__name__)


def get_llama_embed_model() -> BaseEmbedding:
    """Retourne le modèle d'embedding LlamaIndex adapté à l'environnement.

    Utilise GoogleGenAIEmbedding (gemini-embedding-001) si une clé GEMINI_API_KEY
    est présente, sinon bascule sur MockEmbedding pour les tests unitaires / hors-ligne.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        try:
            from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

            return GoogleGenAIEmbedding(
                model_name="gemini-embedding-001",
                api_key=api_key,
            )
        except Exception as e:
            logger.warning(
                f"Impossible d'initialiser GoogleGenAIEmbedding : {e}. Utilisation de MockEmbedding."
            )

    from llama_index.core.embeddings.mock_embed_model import MockEmbedding

    return MockEmbedding(embed_dim=384)


async def build_rag_context(
    loaded_urls: List[str],
    topic: str,
    similarity_top_k: int = 3,
    custom_embed_model: Optional[BaseEmbedding] = None,
) -> Optional[str]:
    """Extrait le texte intégral des articles chargés, l'indexe en mémoire avec LlamaIndex,
    et effectue une recherche de similarité sémantique sur le thème ciblé.

    Retourne les passages les plus pertinents sous forme de texte enrichi pour le prompt
    de la revue de presse, ou None si aucun document ou passage pertinent n'a été trouvé.
    """
    if not loaded_urls:
        return None

    documents: List[Document] = []
    for url in loaded_urls:
        if not url:
            continue
        try:
            article_data = await extract_article_content_api(url)
            text = (article_data.get("text") or "").strip()
            if text and "error" not in article_data:
                title = article_data.get("title") or "Article sans titre"
                author = article_data.get("author") or "Rédaction"
                publish_date = article_data.get("publish_date") or ""
                doc = Document(
                    text=text,
                    metadata={
                        "title": title,
                        "url": url,
                        "author": author,
                        "publish_date": publish_date,
                    },
                )
                documents.append(doc)
        except Exception as e:
            logger.warning(f"Erreur lors de l'extraction de l'article pour RAG ({url}) : {e}")

    if not documents:
        return None

    try:
        embed_model = custom_embed_model or get_llama_embed_model()
        index = VectorStoreIndex.from_documents(documents, embed_model=embed_model)
        retriever = index.as_retriever(similarity_top_k=similarity_top_k)
        nodes = retriever.retrieve(topic)

        if not nodes:
            return None

        rag_parts = ["--- EXTRAITS DE DOCUMENTS ENRICHIS PAR RAG (LLAMAINDEX) ---"]
        rag_parts.append(
            f"Les extraits suivants ont été sélectionnés par recherche sémantique vectorielle dans les articles explorés pour le sujet : '{topic}'\n"
        )

        for i, node in enumerate(nodes, start=1):
            title = node.metadata.get("title", "Article")
            url = node.metadata.get("url", "")
            score_info = f" (score : {node.score:.2f})" if node.score is not None else ""
            content = node.get_content().strip()
            rag_parts.append(
                f"[Source {i} : {title}]({url}){score_info}\n{content}\n"
            )

        rag_parts.append("--- FIN DU CONTEXTE RAG ---\n")
        return "\n".join(rag_parts)
    except Exception as e:
        logger.error(f"Erreur lors de la construction du contexte RAG : {e}")
        return None

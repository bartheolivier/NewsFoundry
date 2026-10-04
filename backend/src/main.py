import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import logging
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
import uvicorn

logger = logging.getLogger("uvicorn.error")

from agent import DEFAULT_SYSTEM_PROMPT, ChatDeps, generate_press_review, run_chat_agent
from auth import create_access_token, get_current_user, verify_password
from database import get_session, init_db
from services.rag import build_rag_context
from models import (
    Chat,
    ChatCreate,
    ChatRead,
    ChatSummary,
    ChatUpdate,
    LoginRequest,
    LoginResponse,
    MessageCreate,
    MessageResponse,
    PressReviewCreate,
    PressReviewItem,
    PressReviewRead,
    User,
    UserRead,
)

from services.world_news import get_top_news_api




@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and default user on application startup
    init_db()
    yield


app = FastAPI(
    title="NewsFoundry API",
    description="API pour l'application d'IA et de revue de presse NewsFoundry",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration to allow requests from Next.js frontend (local & Vercel)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erreur interne du serveur: {str(exc)}"},
    )


@app.get("/")
async def hello():
    return {
        "message": "👋",
        "service": "NewsFoundry API",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "world_news_configured": bool(
            os.getenv("WORLD_NEWS_API_KEY")
            or os.getenv("WORLDNEWS_API_KEY")
            or os.getenv("NEWS_API_KEY")
        ),
    }


@app.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest, session: Session = Depends(get_session)):
    """Authenticates a user and returns a JWT access token."""
    statement = select(User).where(User.email == credentials.email)
    user = session.exec(statement).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserRead(id=user.id, email=user.email),
    )


@app.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user details from the JWT token."""
    return UserRead(id=current_user.id, email=current_user.email)


# --- CHAT ROUTES (PROTECTED WITH USER ISOLATION) ---


@app.get("/chats", response_model=list[ChatSummary])
async def list_chats(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Returns the list of past chat sessions belonging strictly to the authenticated user."""
    statement = (
        select(Chat)
        .where(Chat.user_id == current_user.id)
        .order_by(Chat.updated_at.desc())
    )
    chats = session.exec(statement).all()
    return [
        ChatSummary(
            id=chat.id,
            user_id=chat.user_id,
            title=chat.title,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            message_count=len(chat.messages),
            press_review=chat.press_review,
            loaded_articles=chat.loaded_articles or [],
        )
        for chat in chats
    ]


@app.post("/chats", response_model=ChatRead, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_in: Optional[ChatCreate] = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Creates a new chat session for the authenticated user."""
    now = datetime.now(timezone.utc)
    default_title = f"Discussion du {now.strftime('%d/%m/%Y')}"
    title = (chat_in.title if chat_in and chat_in.title else None) or default_title

    # Fetch top headlines to contextualize the initial system prompt of this discussion
    top_news = await get_top_news_api(country="fr", language="fr")
    context_lines = []
    if top_news:
        context_lines.append("\nActualités phares du jour (contexte initial de la discussion) :")
        for idx, art in enumerate(top_news[:5], 1):
            context_lines.append(f"- {art['title']} : {art['summary']}")

    chat_prompt = (
        DEFAULT_SYSTEM_PROMPT + "\n" + "\n".join(context_lines)
        if context_lines
        else DEFAULT_SYSTEM_PROMPT
    )

    chat = Chat(
        user_id=current_user.id,
        title=title,
        created_at=now,
        updated_at=now,
        messages=[],
        system_prompt=chat_prompt,
        loaded_articles=[],
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)
    if chat.loaded_articles is None:
        chat.loaded_articles = []
    return chat



@app.get("/chats/{chat_id}", response_model=ChatRead)
async def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Retrieves the full message history for a specific chat, enforcing strict user ownership."""
    chat = session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion non trouvée",
        )

    # Security check: verify that this chat belongs to the requesting user
    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès interdit : vous n'êtes pas autorisé à consulter cette discussion.",
        )

    if chat.loaded_articles is None:
        chat.loaded_articles = []
    return chat


@app.delete("/chats/{chat_id}", status_code=status.HTTP_200_OK)
async def delete_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Deletes a chat session belonging strictly to the authenticated user."""
    chat = session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion non trouvée",
        )

    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès interdit : vous n'êtes pas autorisé à supprimer cette discussion.",
        )

    session.delete(chat)
    session.commit()
    return {"message": "Discussion supprimée avec succès", "id": chat_id}


@app.patch("/chats/{chat_id}", response_model=ChatRead)
async def update_chat(
    chat_id: int,
    chat_update: ChatUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Updates the title of a chat session belonging strictly to the authenticated user."""
    chat = session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion non trouvée",
        )

    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès interdit : vous n'êtes pas autorisé à modifier cette discussion.",
        )

    new_title = chat_update.title.strip()
    if not new_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le titre de la discussion ne peut pas être vide.",
        )

    chat.title = new_title
    chat.updated_at = datetime.now(timezone.utc)
    session.add(chat)
    session.commit()
    session.refresh(chat)
    if chat.loaded_articles is None:
        chat.loaded_articles = []
    return chat


@app.post("/chats/{chat_id}/messages", response_model=MessageResponse)
async def send_message(
    chat_id: int,
    message_in: MessageCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Adds a user message to the discussion, calls the PydanticAI agent, and returns the response."""
    chat = session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion non trouvée",
        )

    # Security check: verify that this chat belongs to the requesting user
    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès interdit : vous n'êtes pas autorisé à modifier cette discussion.",
        )

    # Auto-update title if it was generic and this is the first message
    if len(chat.messages) == 0 and chat.title.startswith("Discussion du "):
        auto_title = message_in.content.strip()
        chat.title = auto_title[:35] + ("..." if len(auto_title) > 35 else "")

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()


    # 1. Record user message
    user_msg = {
        "role": "user",
        "content": message_in.content,
        "timestamp": now_iso,
    }

    # 2. Run PydanticAI agent with history and saved discussion prompt
    chat_deps = ChatDeps()
    agent_output = await run_chat_agent(
        chat.messages,
        message_in.content,
        system_prompt_override=chat.system_prompt,
        deps=chat_deps,
    )

    if isinstance(agent_output, tuple):
        assistant_text, new_urls = agent_output
    else:
        assistant_text = agent_output
        new_urls = chat_deps.loaded_articles

    # 3. Record assistant response
    assistant_msg = {
        "role": "assistant",
        "content": assistant_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # 4. Update loaded articles if new articles were fetched during the conversation
    if new_urls:
        existing_urls = list(chat.loaded_articles or [])
        for u in new_urls:
            if u not in existing_urls:
                existing_urls.append(u)
        chat.loaded_articles = existing_urls

    # 5. Persist updated messages and timestamp in database
    chat.messages = list(chat.messages) + [user_msg, assistant_msg]
    chat.updated_at = datetime.now(timezone.utc)
    session.add(chat)
    session.commit()
    session.refresh(chat)

    return MessageResponse(
        role="assistant",
        content=assistant_text,
        timestamp=assistant_msg["timestamp"],
        loaded_articles=chat.loaded_articles or [],
    )


@app.post("/chats/{chat_id}/press-review", response_model=ChatRead)
async def create_chat_press_review(
    chat_id: int,
    review_in: PressReviewCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Génère une revue de presse structurée sur le sujet demandé à partir de l'historique du chat."""
    chat = session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion non trouvée",
        )

    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès interdit : vous n'êtes pas autorisé à modifier cette discussion.",
        )

    topic = review_in.topic.strip()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le thème de la revue de presse ne peut pas être vide.",
        )

    if not chat.messages or len(chat.messages) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de générer une revue de presse à partir d'une discussion vide. Veuillez d'abord échanger avec l'assistant.",
        )

    # 1. Étape 8 : Récupération du contexte RAG à partir des articles explorés
    rag_context = None
    if chat.loaded_articles:
        try:
            rag_context = await build_rag_context(
                loaded_urls=chat.loaded_articles,
                topic=topic,
            )
        except Exception as exc:
            # Fallback gracieux si l'indexation RAG échoue
            print(f"Warning: RAG retrieval failed: {exc}")

    # 2. Appel de l'agent spécialisé de revue de presse avec le contexte RAG enrichi
    generated_output = await generate_press_review(
        chat_messages=chat.messages,
        topic=topic,
        system_prompt=chat.system_prompt,
        rag_context=rag_context,
    )

    review_dict = generated_output.model_dump()
    review_dict["generated_at"] = datetime.now(timezone.utc).isoformat()

    chat.press_review = review_dict
    chat.updated_at = datetime.now(timezone.utc)
    session.add(chat)
    session.commit()
    if chat.loaded_articles is None:
        chat.loaded_articles = []
    return chat


@app.delete("/chats/{chat_id}/press-review", status_code=status.HTTP_200_OK)
async def delete_chat_press_review(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Supprime la revue de presse associée à une discussion de l'utilisateur."""
    chat = session.get(Chat, chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discussion non trouvée",
        )

    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès interdit : vous n'êtes pas autorisé à modifier cette discussion.",
        )

    if not chat.press_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune revue de presse n'est associée à cette discussion.",
        )

    chat.press_review = None
    chat.updated_at = datetime.now(timezone.utc)
    session.add(chat)
    session.commit()
    return {"message": "Revue de presse supprimée avec succès", "chat_id": chat_id}


@app.get("/press-reviews", response_model=list[PressReviewItem])
async def list_press_reviews(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Retourne toutes les revues de presse générées par l'utilisateur connecté sur l'ensemble de ses discussions."""
    statement = (
        select(Chat)
        .where(Chat.user_id == current_user.id)
        .where(Chat.press_review.is_not(None))
        .order_by(Chat.updated_at.desc())
    )
    chats = session.exec(statement).all()

    items: list[PressReviewItem] = []
    for chat in chats:
        if chat.press_review:
            items.append(
                PressReviewItem(
                    chat_id=chat.id,
                    chat_title=chat.title,
                    press_review=PressReviewRead(**chat.press_review),
                )
            )
    return items


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)



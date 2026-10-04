import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
import uvicorn

from agent import DEFAULT_SYSTEM_PROMPT, run_chat_agent
from auth import create_access_token, get_current_user, verify_password
from database import get_session, init_db
from models import (
    Chat,
    ChatCreate,
    ChatRead,
    ChatSummary,
    LoginRequest,
    LoginResponse,
    MessageCreate,
    MessageResponse,
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


@app.get("/")
async def hello():
    return {"message": "👋", "service": "NewsFoundry API"}


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
    )
    session.add(chat)
    session.commit()
    session.refresh(chat)
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

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    # 1. Record user message
    user_msg = {
        "role": "user",
        "content": message_in.content,
        "timestamp": now_iso,
    }

    # 2. Run PydanticAI agent with history and saved discussion prompt
    assistant_text = await run_chat_agent(
        chat.messages,
        message_in.content,
        system_prompt_override=chat.system_prompt,
    )


    # 3. Record assistant response
    assistant_msg = {
        "role": "assistant",
        "content": assistant_text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # 4. Persist updated messages and timestamp in database
    chat.messages = list(chat.messages) + [user_msg, assistant_msg]
    chat.updated_at = datetime.now(timezone.utc)
    session.add(chat)
    session.commit()
    session.refresh(chat)

    return MessageResponse(
        role="assistant",
        content=assistant_text,
        timestamp=assistant_msg["timestamp"],
    )



if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)



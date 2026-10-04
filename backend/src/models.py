from datetime import datetime, timezone
from typing import Any, List, Optional
from pydantic import BaseModel
from sqlmodel import Column, DateTime, Field, JSON, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str = Field()


class Chat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(default="Nouvelle discussion")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    # Complete conversation message history stored as JSON:
    # List of {"role": "user"|"assistant", "content": "...", "timestamp": "..."}
    messages: List[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False),
    )
    system_prompt: Optional[str] = Field(default=None)
    press_review: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )



class UserRead(BaseModel):
    id: int
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class ChatCreate(BaseModel):
    title: Optional[str] = None


class ChatUpdate(BaseModel):
    title: str



class ChatSummary(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    press_review: Optional[dict[str, Any]] = None


class ChatRead(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[dict[str, Any]]
    system_prompt: Optional[str] = None
    press_review: Optional[dict[str, Any]] = None


class ArticleSummary(BaseModel):
    title: str = Field(description="Titre de l'article")
    source: Optional[str] = Field(default=None, description="Nom du média, auteur ou source")
    url: Optional[str] = Field(default=None, description="Lien URL d'origine vers l'article si mentionné")
    summary: str = Field(description="Synthèse concise des points clés apportés par l'article")


class PressReviewOutput(BaseModel):
    title: str = Field(description="Titre percutant de la revue de presse en majuscules (ex: ACTUALITÉS POLITIQUES - SEMAINE 39)")
    topic: str = Field(description="Thème ou sujet de la revue de presse")
    general_summary: str = Field(description="Synthèse globale claire et structurée des événements et enjeux majeurs")
    articles: List[ArticleSummary] = Field(default_factory=list, description="Liste des synthèses des articles pertinents abordés")
    perspectives: Optional[str] = Field(default=None, description="Perspectives d'évolution, calendrier à venir ou conclusion")


class PressReviewRead(BaseModel):
    title: str
    topic: str
    general_summary: str
    articles: List[ArticleSummary] = Field(default_factory=list)
    perspectives: Optional[str] = None
    generated_at: str


class PressReviewCreate(BaseModel):
    topic: str


class PressReviewItem(BaseModel):
    chat_id: int
    chat_title: str
    press_review: PressReviewRead



class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: str



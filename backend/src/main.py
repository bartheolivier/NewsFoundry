import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
import uvicorn

from auth import create_access_token, get_current_user, verify_password
from database import get_session, init_db
from models import LoginRequest, LoginResponse, User, UserRead


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


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)



# 🚀 Guide de Démarrage et d'Exécution des Tests — NewsFoundry

Ce guide fournit l'ensemble des instructions nécessaires pour installer le projet, démarrer l'environnement en local, exécuter les tests automatisés et déployer l'application.

---

## 📋 1. Prérequis Système

- **Python** : version 3.13 recommandée (gérée automatiquement via `uv`)
- **uv** : gestionnaire de paquets et de runtimes Python ultra-rapide ([installer uv](https://docs.astral.sh/uv/getting-started/installation/))
- **Node.js** : version 22+ (avec npm)
- **Docker** : pour démarrer facilement une instance PostgreSQL en local

---

## ⚙️ 2. Configuration des Variables d'Environnement

### Backend (`backend/.env`)
Créez un fichier `.env` dans le dossier `backend/` en vous basant sur `backend/.env.example` :

```env
# Sécurité JWT & Compte d'accès initial (à personnaliser impérativement en production Railway)
SECRET_KEY="newsfoundry-secret-key-development-2026"
DEMO_USER_EMAIL="test@test.com"
DEMO_USER_PASSWORD="test"

# Protection CORS & Garde-fous FinOps (anti-bruteforce et plafond quotidien IA)
CORS_ORIGINS="*"
MAX_LOGIN_ATTEMPTS=8
MAX_DAILY_AI_CALLS=100

# Base de Données PostgreSQL
DATABASE_URL="postgresql://user:password@localhost:5432/newsfoundry"

# Fournisseur LLM (Gemini par défaut)
GEMINI_API_KEY="votre_cle_api_gemini"
LLM_MODEL="gemini-3.5-flash-lite"

# API d'actualités (WorldNewsAPI)
WORLD_NEWS_API_KEY="votre_cle_api_worldnews"

# Port d'écoute du serveur
PORT=8000
```

### Frontend (`frontend/.env.local`)
Créez un fichier `.env.local` dans le dossier `frontend/` :

```env
NEXT_PUBLIC_API_URL="http://localhost:8000"
# En production (Vercel), le bouton d'auto-connexion démo est masqué par défaut (NODE_ENV=production)
# NEXT_PUBLIC_SHOW_DEMO_CREDENTIALS="false"
```

---

## 💻 3. Démarrage de l'Application en Local

### A. Lancer la Base de Données PostgreSQL
Dans un terminal, démarrez le conteneur Docker PostgreSQL :

```bash
docker run -d \
  --name newsfoundry_db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=newsfoundry \
  -p 5432:5432 \
  postgres:17
```

### B. Démarrer le Backend FastAPI
Depuis la racine du projet ou depuis `backend/` :

```bash
cd backend

# Synchronisation des dépendances dans l'environnement virtuel .venv
uv sync

# Lancement du serveur avec rechargement à chaud
PYTHONPATH=src uv run --env-file .env uvicorn main:app --reload --port 8000
```
Le backend sera accessible sur `http://localhost:8000` et la documentation interactive sur `http://localhost:8000/docs`.

### C. Démarrer le Frontend Next.js
Dans un second terminal :

```bash
cd frontend

# Installation des dépendances npm
npm install

# Démarrage du serveur de développement Next.js (Turbopack)
npm run dev
```
L'interface utilisateur sera accessible sur `http://localhost:3000`.

### D. Scripts d'Automatisation Globale (Démonstration rapide)
Pour simplifier le lancement lors des sessions de développement et de démonstration mentor, des scripts d'orchestration sont mis à disposition à la racine du projet :

```bash
# Lancer l'intégralité de la stack locale (PostgreSQL + Backend + Frontend)
./start_all.sh

# Vérifier le statut de tous les services (BD, API, UI)
./status_all.sh

# Arrêter proprement tous les services locaux
./stop_all.sh

# Scripts de gestion granulaire par composant :
./start_backend.sh   # Lance uniquement l'API FastAPI (port 8000)
./stop_backend.sh    # Arrête l'API FastAPI
./start_frontend.sh  # Lance uniquement l'UI Next.js (port 3000)
./stop_frontend.sh   # Arrête l'UI Next.js
./start_db.sh        # Lance PostgreSQL (port 5433)
./stop_db.sh         # Arrête PostgreSQL
```

---

## 🧪 4. Exécution des Tests Automatisés

Le backend dispose d'une suite de **62 tests automatisés** couvrant l'intégralité du cycle de vie de l'application (authentification, sécurité multi-tenant, rotation des identifiants en production, protection anti-bruteforce, plafond quotidien de requêtes IA, gestion d'erreurs WorldNewsAPI, filtrage anti-bruit des manchettes, déduplication des dépêches syndiquées, cache multi-pays des Breaking News, garantie déterministe des sources, gestion des quotas LLM, synthèse de revue de presse et indexation RAG LlamaIndex).

### A. Lancer l'Intégralité de la Suite de Tests Backend
Depuis le dossier `backend/` :

```bash
PYTHONPATH=src uv run --env-file .env pytest -v
```

### B. Lancer un Module de Test Spécifique

```bash
# Tests de garantie déterministe des sources, déduplication et formatage Markdown (6 tests)
PYTHONPATH=src uv run --env-file .env pytest tests/test_sources.py -v

# Tests RAG et indexation vectorielle LlamaIndex (6 tests)
PYTHONPATH=src uv run --env-file .env pytest tests/test_rag.py -v

# Tests de la revue de presse et Structured Outputs (7 tests)
PYTHONPATH=src uv run --env-file .env pytest tests/test_press_review.py -v

# Tests de sécurité des discussions, isolation multi-utilisateurs, /top-news et erreurs IA (14 tests)
PYTHONPATH=src uv run --env-file .env pytest tests/test_chats.py -v

# Tests d'authentification JWT, rotation de mot de passe, anti-bruteforce et plafond FinOps (11 tests)
PYTHONPATH=src uv run --env-file .env pytest tests/test_auth.py -v

# Tests WorldNewsAPI, filtrage anti-bruit, déduplication, cache multi-pays et erreurs HTTP (18 tests)
PYTHONPATH=src uv run --env-file .env pytest tests/test_world_news.py -v
```

### C. Validation Frontend (TypeScript & Next.js Build)
Depuis le dossier `frontend/` :

```bash
# Vérification du typage TypeScript et compilation Next.js
npm run build

# Analyse de code statique ESLint
npm run lint
```

---

## 🌐 5. Environnements de Déploiement Cloud (Production)

- **Frontend :** Déployé en continu sur **Vercel** (`Root Directory: frontend`).
- **Backend & Base PostgreSQL 17 :** Déployés via conteneur Docker sur **Railway** (`Root Directory: backend`).
- **Confidentialité & Maîtrise FinOps :** Afin de protéger les abonnements d'APIs facturés à l'usage (Google Gemini & WorldNewsAPI), les URLs publiques de production ainsi que les identifiants dédiés (`DEMO_USER_EMAIL` / `DEMO_USER_PASSWORD`) ne figurent pas dans le dépôt Git public et sont transmis de manière confidentielle au jury lors du dépôt du livrable.

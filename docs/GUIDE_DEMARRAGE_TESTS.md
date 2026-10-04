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
Créez un fichier `.env` dans le dossier `backend/` en vous basant sur l'exemple ci-dessous :

```env
# Sécurité & JWT
SECRET_KEY="newsfoundry-secret-key-development-2026"

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

---

## 🧪 4. Exécution des Tests Automatisés

Le backend dispose d'une suite de **45 tests automatisés** couvrant l'intégralité du cycle de vie de l'application (authentification, sécurité multi-tenant, gestion d'erreurs WorldNewsAPI, synthèse de revue de presse et indexation RAG LlamaIndex).

### A. Lancer l'Intégralité de la Suite de Tests Backend
Depuis le dossier `backend/` :

```bash
PYTHONPATH=src uv run --env-file .env pytest -v
```

### B. Lancer un Module de Test Spécifique

```bash
# Tests RAG et indexation vectorielle LlamaIndex (6 tests)
PYTHONPATH=src uv run --env-file .env pytest tests/test_rag.py -v

# Tests de la revue de presse et Structured Outputs (7 tests)
PYTHONPATH=src uv run --env-file .env pytest tests/test_press_review.py -v

# Tests de sécurité des discussions et isolation multi-utilisateurs (12 tests)
PYTHONPATH=src uv run --env-file .env pytest tests/test_chats.py -v

# Tests d'authentification JWT et hachage de mot de passe (7 tests)
PYTHONPATH=src uv run --env-file .env pytest tests/test_auth.py -v

# Tests des outils WorldNewsAPI et résilience aux erreurs HTTP (13 tests)
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

- **Frontend (Vercel) :** [https://news-foundry-6qc6tpcon-bartheoliviers-projects.vercel.app](https://news-foundry-6qc6tpcon-bartheoliviers-projects.vercel.app)
- **Backend (Railway) :** [https://newsfoundry-production-e3fe.up.railway.app](https://newsfoundry-production-e3fe.up.railway.app)
- **Documentation API Swagger en Production :** [https://newsfoundry-production-e3fe.up.railway.app/docs](https://newsfoundry-production-e3fe.up.railway.app/docs)

# 📰 NewsFoundry

> **Plateforme SaaS d'assistance journalistique par IA et de génération de revues de presse automatiques enrichies par RAG.**

NewsFoundry accompagne les journalistes, pigistes et professionnels de l'information dans leurs travaux d'investigation : recherche d'actualités mondiales en temps réel, fact-checking, lecture approfondie d'articles et rédaction automatisée de revues de presse thématiques hautement qualifiées grâce à **PydanticAI** et **LlamaIndex**.

---

## 🌐 Déploiements Cloud en Production (Vercel & Railway)

L'application est déployée en intégration et déploiement continus (CI/CD) :
- **Interface Frontend :** Hébergée sur **Vercel** (Next.js App Router).
- **API Backend & Base de Données :** Conteneur Docker FastAPI et instance PostgreSQL 17 managée sur **Railway**.

> 🔒 **Note de sécurité & maîtrise des coûts (DevSecOps / FinOps) :**  
> L'application s'appuyant en production sur des APIs facturées à l'usage (**Google Gemini** et **WorldNewsAPI**), les URLs publiques de déploiement ainsi que les identifiants d'accès ne sont pas exposés dans ce dépôt public afin de prévenir toute utilisation automatisée non autorisée. Ils sont communiqués directement au jury dans le dossier de remise de la soutenance.

---

## 📚 Documentation Technique Détaillée

Pour faciliter la prise en main et limiter toute perte de contexte, la documentation technique est organisée dans le dossier [`docs/`](docs/) :

- 🏛️ **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** : Architecture globale du système, arborescence complète du code source, diagrammes de séquence et flux de données.
- 🎯 **[docs/CHOIX_TECHNIQUES.md](docs/CHOIX_TECHNIQUES.md)** : Justification détaillée de chaque choix technologique (Next.js 16, FastAPI, SQLModel, PydanticAI, LlamaIndex, PostgreSQL, UV).
- 🚀 **[docs/GUIDE_DEMARRAGE_TESTS.md](docs/GUIDE_DEMARRAGE_TESTS.md)** : Guide pas-à-pas pour l'installation, le paramétrage des variables d'environnement et l'exécution des tests automatisés.
- ⚡ **[docs/AMELIORATIONS_PERFORMANCE.md](docs/AMELIORATIONS_PERFORMANCE.md)** : Analyse critique de performance, métriques UX (Jakob Nielsen), streaming SSE, observabilité MLOps avec MLflow et optimisations RAG.

---

## ✨ Fonctionnalités Clés

1. **Authentification & Sécurité Multi-Tenant :**
   - Connexion sécurisée par tokens JWT avec expiration à 24h et hachage de mot de passe `bcrypt`.
   - Isolation stricte des données : chaque journaliste n'a accès qu'à ses propres discussions et revues de presse (rejet HTTP 403 Forbidden sur toute tentative d'accès non autorisé).
2. **Breaking News en Temps Réel & Sélecteur Multi-Pays :**
   - Affichage dynamique des 3 actualités phares du jour sur la carte d'accueil avec sélecteur de pays (🇫🇷 France par défaut, 🇺🇸 États-Unis, 🇬🇧 Royaume-Uni, 🇩🇪 Allemagne).
   - Filtrage heuristique anti-bruit (exclusion automatique des podcasts, bulletins météo, loteries et jeux quotidiens type *Wordle* / *NYT Connections*) et mise en cache mémoire d'une heure isolée par pays pour préserver le quota d'API.
3. **Agent de Chat Journaliste (PydanticAI) :**
   - Recherche en direct des actualités mondiales via l'outil `search_news` (WorldNewsAPI) avec nettoyage automatique des requêtes et ciblage géographique/linguistique des médias locaux (synthèse toujours restituée en français).
   - Lecture approfondie et extraction du contenu textuel intégral via l'outil `get_article_content`.
   - Déduplication lexicale et par URL canonique des dépêches d'agences syndiquées, et citation systématique des sources garantie de manière déterministe par le code (`ensure_sources_section`).
   - Suivi transparent des articles explorés grâce à l'injection de dépendances `RunContext[ChatDeps]`.
4. **Indexation Vectorielle RAG en Mémoire (LlamaIndex) :**
   - Indexation vectorielle éphémère (`VectorStoreIndex`) sans base vectorielle externe lourde.
   - Recherche sémantique ciblée sur le thème de la revue de presse pour extraire uniquement les segments d'articles les plus denses et pertinents.
5. **Agent Spécialisé de Revue de Presse (*Structured Outputs*) :**
   - Second agent dédié agissant comme rédacteur en chef expert.
   - Sorties strictement typées via le schéma `PressReviewOutput` (titre, thème, synthèse globale, résumés d'articles, perspectives).
   - Onglet dédié permettant de consulter, copier en un clic et supprimer les revues de presse générées.

---

## ⚡ Démarrage Rapide en Local

### 1. Prérequis
- Docker
- Python 3.13 (géré par [uv](https://docs.astral.sh/uv/))
- Node.js 22+

### 2. Base de Données
```bash
docker run -d --name newsfoundry_db -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=newsfoundry -p 5432:5432 postgres:17
```

### 3. Backend
```bash
cd backend
cp .env.example .env    # Configurer GEMINI_API_KEY et WORLD_NEWS_API_KEY
uv sync
PYTHONPATH=src uv run --env-file .env uvicorn main:app --reload --port 8000
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```
Accédez ensuite à `http://localhost:3000`.

---

## 🧪 Tests Automatisés (62 tests)

Le projet intègre une suite complète de **62 tests automatisés** validés dans le pipeline d'intégration continue GitHub Actions :

```bash
cd backend
PYTHONPATH=src uv run --env-file .env pytest -v
```

Vérification du frontend Next.js :
```bash
cd frontend
npm run build
npm run lint
```

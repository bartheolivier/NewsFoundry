# 🎯 Justification des Choix Techniques — NewsFoundry

Ce document détaille l'ensemble des choix d'architecture, de frameworks, de bibliothèques et de modélisation retenus pour la conception de **NewsFoundry**, ainsi que les raisons objectives de ces décisions.

---

## 1. Stack Backend : Python 3.13, FastAPI & SQLModel

### A. Pourquoi Python 3.13 ?
- **Écosystème IA natif :** Python demeure le standard incontournable pour l'ingénierie de l'intelligence artificielle (PydanticAI, LlamaIndex, SDKs Google GenAI / OpenAI).
- **Performances asynchrones accrues :** Les améliorations continues du moteur d'exécution et de l'asynchronisme (`asyncio`) permettent de gérer efficacement les multiples appels d'APIs externes sans bloquer le serveur.

### B. Pourquoi FastAPI ?
- **Performances & Asynchronisme :** Conçu nativement sur `Starlette` et `uvicorn`, FastAPI excelle dans la manipulation d'opérations I/O intensives (appels LLM, requêtes HTTP vers WorldNewsAPI, requêtes SQL).
- **Validation stricte & Typage :** Basé sur Pydantic v2, chaque requête et réponse d'API est automatiquement validée et typée à la compilation et à l'exécution.
- **Documentation interactive OpenAPI :** Génération automatique de la documentation Swagger (`/docs`) facilitant le débogage et l'intégration continue.

### C. Pourquoi SQLModel & PostgreSQL 17 ?
- **Unicité des schémas :** SQLModel combine la puissance déclarative de SQLAlchemy et la validation de Pydantic. Une seule classe définit à la fois la table de base de données et le modèle de validation applicatif, éliminant la duplication de code et les erreurs de mapping.
- **Colonnes JSON natives de PostgreSQL :** Les conversations journalistiques (`chat.messages`), les métadonnées de revues de presse (`chat.press_review`) et les articles explorés (`chat.loaded_articles`) sont stockés dans des colonnes de type `JSON`. Cela offre la flexibilité du NoSQL (historique imbriqué, métadonnées évolutives) tout en conservant la rigueur et l'intégrité relationnelle d'une base SQL (clés étrangères `user_id`, index, transactions ACID).

---

## 2. Gestionnaire de Dépendances : UV d'Astral

- **Vitesse fulgurante :** Développé en Rust par Astral, `uv` est 10 à 100 fois plus rapide que `pip`, `pipenv` ou `poetry`.
- **Fichier de verrouillage déterministe (`uv.lock`) :** Garantit une reproductibilité absolue des builds entre l'environnement de développement local, les conteneurs Docker de test et la plateforme de production Railway.
- **Gestion intégrée des runtimes Python :** Permet d'épingler et d'exécuter Python 3.13 avec une isolation stricte des environnements virtuels (`backend/.venv`).

---

## 3. Framework d'Agents IA : PydanticAI

Plutôt que des frameworks massifs et complexes comme LangChain ou AutoGen, nous avons sélectionné **PydanticAI** :

### A. Séparation en Deux Agents Spécialisés
Conformément aux bonnes pratiques d'ingénierie de l'IA (et aux recommandations d'OpenClassrooms) :
1. **Agent d'Exploration & Chat (`get_agent`) :**
   - Équipé d'outils externes (`search_news`, `get_article_content`).
   - Rôle : Chercheur d'investigation en temps réel, fact-checking, veille d'actualité.
2. **Agent de Synthèse de Revue de Presse (`get_press_review_agent`) :**
   - **Aucun outil externe.**
   - Rôle : Rédacteur en chef expert.
   - **Bénéfice :** Élimine tout risque d'appels d'outils circulaires superflus, divise la latence par deux et concentre 100 % des tokens sur la structuration journalistique.

### B. Sorties Structurées (*Structured Outputs*)
- Grâce à `output_type=PressReviewOutput`, le modèle génère directement un format JSON garanti par schéma Pydantic, sans nécessiter de parseur de texte ou d'expressions régulières fragiles.
- En cas d'incohérence, PydanticAI effectue un retry automatique en renvoyant l'erreur de validation directement au LLM.

### C. Injection de Dépendances (`ChatDeps`)
- L'outil `get_article_content(ctx: RunContext[Optional[ChatDeps]], url: str)` utilise le système d'injection de dépendances pour capturer l'URL lue dans la session sans polluer la signature d'outil exposée au modèle.

---

## 4. Système RAG : LlamaIndex en Mémoire (*In-Memory Vector Store*)

### A. Pourquoi LlamaIndex ?
LlamaIndex est le framework de référence pour la connectivité entre documents réels et modèles de langage (découpage intelligent, embeddings, nœuds documentaires et retrievers).

### B. Pourquoi un Index Vectoriel en Mémoire Vive ?
Plutôt que d'introduire une base de données vectorielle externe complexe et payante (comme Pinecone ou Qdrant) :
- **Légèreté & Coût nul :** Les sessions d'enquête impliquent généralement entre 2 et 10 articles clés.
- **Indexation instantanée :** `VectorStoreIndex.from_documents` s'indexe en quelques millisecondes dans la RAM du backend FastAPI.
- **Confidentialité absolue :** L'index est éphémère. Sitôt la revue de presse générée, il est libéré de la mémoire. Aucune donnée d'investigation ne reste stockée dans une base vectorielle partagée.

### C. Stratégie d'Embeddings Hybride
- **En Production :** `GoogleGenAIEmbedding` avec le modèle `gemini-embedding-001` (vecteurs de taille 3072), entièrement pris en charge par la clé d'API Gemini existante.
- **En Tests Automatisés :** `MockEmbedding(embed_dim=384)` de LlamaIndex, garantissant une exécution 100 % hors-ligne, ultra-rapide et reproductible des tests sans quota d'API.

---

## 5. Frontend : Next.js 16 (App Router), React 19 & CSS Modules

- **App Router & Turbopack :** Vitesse de compilation ultra-rapide en développement et rendu optimisé en production.
- **Conformité aux Maquettes Figma :** L'interface a été conçue sur-mesure avec CSS Modules (`page.module.css`), sans recourir à des bibliothèques de composants tierces génériques (type MUI ou Bootstrap). Cela assure un respect au pixel près des maquettes (palette de couleurs, typographie, espacements, réactivité mobile).
- **Rendu Markdown Sécurisé :** Intégration de `react-markdown` pour restituer avec fidélité les titres, listes, citations et liens hypertextes des sources de presse.
- **Gestion de l'État Réactif :** Synchronisation immédiate des discussions et des métadonnées RAG sans aucun besoin de rafraîchissement manuel de page (F5).

---

## 6. Authentification & Sécurité Multi-Tenant

- **Tokens JWT Stateless :** Signature cryptographique HMAC-SHA256 avec expiration à 24 heures.
- **Chiffrement des Mots de Passe :** Hachage robuste via `bcrypt` avec génération de sel unique (*salt*).
- **Isolation Stricte (403 Forbidden) :** Chaque endpoint vérifie rigoureusement que la ressource demandée (`chat_id`) appartient au `user_id` extrait du token. Aucun utilisateur ne peut accéder, modifier ou supprimer le travail d'un confrère.

---

## 7. Déploiement & Cloud

- **Backend sur Railway :** Déploiement automatisé par conteneur Docker avec base PostgreSQL 17 managée.
- **Frontend sur Vercel :** Intégration native avec Next.js pour des performances de distribution CDN mondiales et temps de réponse minimaux.

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

---

## 8. Les Raisons des Choix de Prompts (*Prompt Engineering*)

La conception des prompts système a été pensée pour répondre rigoureusement aux impératifs d'un produit SaaS dédié aux journalistes professionnels : **objectivité, vérifiabilité des faits, contextualisation immédiate et délimitation stricte des rôles**.

### A. Prompt Système de l'Agent de Chat Journaliste (`DEFAULT_SYSTEM_PROMPT`)

```text
Tu es l'assistant IA de NewsFoundry, une plateforme SaaS dédiée aux journalistes, pigistes et professionnels des médias.
Ton rôle est d'aider les journalistes à explorer l'actualité, synthétiser des événements récents, répondre à leurs questions d'investigation et préparer des revues de presse.

Règles impératives :
1. Recherche d'actualités en direct : Tu as accès à l'outil `search_news`. Utilise-le SYSTÉMATIQUEMENT dès que la question de l'utilisateur porte sur des événements récents, des actualités du jour...
2. Lecture approfondie d'articles : Tu as accès à l'outil `get_article_content`. Utilise-le dès que l'utilisateur demande des précisions...
3. Démarche journalistique : Adopte un ton journalistique, professionnel, objectif, clair et structuré.
4. Formattage Markdown : Structure tes réponses avec soin en utilisant du Markdown...
5. CITATION DES SOURCES : Lorsque tu utilises des informations issues de tes outils, mentionne systématiquement la source/le média et inclus les liens markdown vers les articles originaux (ex: [Titre de l'article](url)).
6. Transparence : Si aucun article n'est trouvé ou si une erreur survient... informe clairement l'utilisateur...
```

**Justifications des choix :**
1. **Règle de citation systématique (Règle 5) :** Dans le journalisme, une information sans source vérifiable est inutilisable. Le prompt force le modèle à mentionner la source et à formater les liens markdown `[Titre](URL)` pour que le journaliste puisse remonter à la source originale en un clic.
2. **Déclenchement systématique des outils (Règles 1 et 2) :** Les LLMs ont tendance à s'appuyer sur leur mémoire statique datée. Les consignes explicites imposent d'invoquer `search_news` pour l'actualité chaude et `get_article_content` pour les analyses en profondeur.
3. **Ton et posture déontologique (Règle 3) :** Imposer un ton neutre, factuel et structuré évite les tournures flatteuses ou les jugements de valeur inappropriés pour une rédaction.
4. **Contextualisation dynamique initiale (`/top-news`) :** Lors de la création d'une nouvelle discussion, l'API interroge les manchettes phares du jour via WorldNewsAPI et les injecte dans le `system_prompt` de la session. Cela permet à l'assistant d'être immédiatement au fait de l'actualité du jour dès le premier message, sans attendre une question explicite.

---

### B. Prompt Système de l'Agent de Revue de Presse (`PRESS_REVIEW_SYSTEM_PROMPT`)

```text
Tu es le rédacteur en chef expert de NewsFoundry, spécialisé dans la rédaction de revues de presse journalistiques de référence.
Ton rôle est d'analyser l'intégralité des recherches, dépêches, articles et échanges issus d'une discussion journalistique pour composer une revue de presse structurée, claire, neutre et percutante sur le thème demandé.

Règles impératives de rédaction :
1. Titre : Propose un grand titre en majuscules (ex: 'REVUE DE PRESSE : TRANSITION ÉNERGÉTIQUE ET MOBILITÉ ÉLECTRIQUE').
2. Thème : Rappelle le sujet ciblé.
3. Synthèse générale : Développe une synthèse d'ensemble soignée (2 à 4 paragraphes) articulant les faits essentiels, chiffres marquants et tendances de fond.
4. Synthèse des articles : Identifie tous les articles clés et sources cités dans la discussion se rapportant au thème...
5. Perspectives : Conclus avec les enjeux d'avenir, les prochaines échéances ou les questions en suspens.
6. Structured Output : Respecte rigoureusement le schéma JSON imposé.
```

**Justifications des choix :**
1. **Rôle de Rédacteur en Chef :** Contrairement au rôle d'enquêteur interactif du chat, ce prompt positionne le modèle comme un décideur de rédaction qui priorise, hiérarchise et synthétise les faits denses.
2. **Harmonisation avec le schéma Pydantic (`PressReviewOutput`) :** Les règles 1 à 5 correspondent exactement aux champs du modèle de données, ce qui guide le modèle dans la génération de chaque bloc du schéma JSON sans hallucination de format.
3. **Perspectives d'avenir :** Une revue de presse journalistique professionnelle ne se contente pas de relater le passé ; elle doit éclairer les prochaines étapes, les échéances légales ou les débats à venir.

---

## 9. Répertoire Exhaustif des Erreurs Retournées par l'API Backend

Pour garantir une intégration robuste et informer l'utilisateur de manière précise, l'API FastAPI utilise des codes de statut HTTP standardisés avec des messages d'erreur explicites au format JSON `{ "detail": "..." }`.

| Endpoint | Code HTTP | Raison / Scénario de déclenchement | Exemple de payload retourné |
| :--- | :---: | :--- | :--- |
| `POST /login` | **401 Unauthorized** | Email inconnu ou mot de passe invalide | `{"detail": "Email ou mot de passe incorrect."}` |
| `GET /me` | **401 Unauthorized** | Token JWT manquant, invalide ou expiré | `{"detail": "Token d'authentification invalide ou expiré."}` |
| `GET /chats/{id}` | **404 Not Found** | La discussion demandée n'existe pas en BDD | `{"detail": "Discussion non trouvée"}` |
| `GET /chats/{id}` | **403 Forbidden** | La discussion appartient à un autre utilisateur | `{"detail": "Accès interdit : vous n'êtes pas autorisé à consulter cette discussion."}` |
| `PATCH /chats/{id}` | **400 Bad Request** | Le nouveau titre fourni est vide ou constitué uniquement d'espaces | `{"detail": "Le titre de la discussion ne peut pas être vide."}` |
| `PATCH /chats/{id}` | **403 Forbidden** | Tentative de renommage d'une discussion d'un autre utilisateur | `{"detail": "Accès interdit : vous n'êtes pas autorisé à modifier cette discussion."}` |
| `DELETE /chats/{id}` | **403 Forbidden** | Tentative de suppression d'une discussion appartenant à un confrère | `{"detail": "Accès interdit : vous n'êtes pas autorisé à supprimer cette discussion."}` |
| `DELETE /chats/{id}` | **404 Not Found** | Discussion à supprimer introuvable | `{"detail": "Discussion non trouvée"}` |
| `POST /chats/{id}/messages` | **400 Bad Request** | Message vide ou payload JSON malformé | `{"detail": "Le contenu du message ne peut pas être vide."}` |
| `POST /chats/{id}/messages` | **403 Forbidden** | Envoi d'un message sur la discussion d'un autre utilisateur | `{"detail": "Accès interdit : vous n'êtes pas autorisé à modifier cette discussion."}` |
| `POST /chats/{id}/press-review`| **400 Bad Request** | Le thème de revue de presse fourni est vide | `{"detail": "Le thème de la revue de presse ne peut pas être vide."}` |
| `POST /chats/{id}/press-review`| **400 Bad Request** | Tentative de génération sur une discussion vide (sans messages) | `{"detail": "Impossible de générer une revue de presse à partir d'une discussion vide..."}` |
| `POST /chats/{id}/press-review`| **403 Forbidden** | Génération demandée sur une discussion non possédée | `{"detail": "Accès interdit : vous n'êtes pas autorisé à modifier cette discussion."}` |
| `DELETE /chats/{id}/press-review`| **404 Not Found** | Aucune revue de presse n'existe sur cette discussion | `{"detail": "Aucune revue de presse n'est associée à cette discussion."}` |
| `DELETE /chats/{id}/press-review`| **403 Forbidden** | Tentative de suppression de la revue de presse d'un confrère | `{"detail": "Accès interdit : vous n'êtes pas autorisé à modifier cette discussion."}` |


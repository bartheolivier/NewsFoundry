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
- L'outil `get_article_content(ctx: RunContext[Optional[ChatDeps]], url: str)` et `search_news(ctx: RunContext[Optional[ChatDeps]], ...)` utilisent le système d'injection de dépendances pour capturer en temps réel l'ensemble des articles consultés (`loaded_articles`) et leurs métadonnées (`turn_sources`) sans polluer la signature d'outil exposée au modèle.

### D. Garantie Déterministe des Citations & Liens Cliquables (Code-Level Guarantee)
- **Le problème de l'auto-conditionnement en multi-tours :** Lors de conversations longues, si le modèle répond une seule fois de manière narrative sans liens, il a tendance, aux tours suivants, à imiter son propre style précédent plutôt que d'obéir aux instructions du système (*in-context mimicry*). De plus, l'éloignement physique entre le prompt initial et le flux des résultats d'outils dilue l'attention des modèles légers (*flash-lite*).
- **La solution par le code (`ensure_sources_section`) :**
  1. Chaque article reçu via `search_news` ou `get_article_content` est automatiquement consigné dans `deps.turn_sources` avec son titre, URL, source et date.
  2. Un rappel direct (`CITATION_REMINDER`) est greffé immédiatement après le résultat de l'outil, là où le modèle lit les données fraîches.
  3. En fin d'exécution de `run_chat_agent`, une vérification déterministe s'assure que si des articles ont été consultés, la section `### 📰 Sources consultées` est présente avec les liens hypertextes valides. Si le modèle l'a omise, elle est injectée automatiquement par le code.
  - **Bénéfice :** Aucun lien ne peut être halluciné (seuls les articles réels issus de l'API sont listés) et aucune réponse documentée ne peut être privée de ses sources cliquables.

### E. Résilience des Requêtes de Recherche (`_simplify_query`)
- WorldNewsAPI effectue une recherche stricte par mots-clés. Si un LLM génère une phrase de 8 mots (ex: *« marches asiatiques bourses bourse de tokyo shanghai »*), l'API renvoie 0 article.
- Une fonction de nettoyage élimine les mots parasites (*actualite, presse, bourse, sur, les, de...*) et, en cas de résultat nul, relance automatiquement une requête ciblée sur les 2 ou 3 termes les plus discriminants, divisant le taux de recherche infructueuse par dix.

### F. Déduplication Lexicale & Canonique des Dépêches (`deduplicate_news_articles`)
- Dans la presse en ligne, une même dépêche d'agence (AFP, AP, Reuters) est souvent reprise mot pour mot par plusieurs quotidiens régionaux sous des URLs différentes ou avec des paramètres de tracking (`?utm_source=...`).
- Le backend normalise chaque URL (`canonical_url`) et applique un calcul de similarité lexicale de Jaccard sur les mots significatifs des titres (seuil `>= 70 %`), tant à la réception des articles WorldNewsAPI que lors du formatage final de la section `Sources consultées`. Chaque source présentée au journaliste correspond ainsi à un article unique et distinct.

### G. Ciblage Multi-Pays, Filtrage Anti-Bruit & Cache Compartimenté
- **Sélecteur international (FR, US, UK, DE) :** Le journaliste peut explorer les actualités phares par pays tout en conservant une synthèse rédigée en français. Une double sécurité (consignes dans `DEFAULT_SYSTEM_PROMPT` + détection heuristique de secours en Python dans `search_news`) garantit l'interrogation directe des médias nationaux dans leur langue d'origine (`en`/`us`, `en`/`gb`, `de`/`de`, `fr`/`fr`), évitant de citer une simple reprise française pour un événement américain.
- **Filtrage qualitatif (`is_relevant_headline`) :** Un moteur d'expressions régulières écarte automatiquement des Breaking News les contenus à fort volume mais sans valeur d'investigation (grilles radio, podcasts, bulletins météo, tirages de loterie *Powerball / Loto*, et guides de jeux quotidiens type *NYT Connections / Wordle*).
- **Cache mémoire isolé 1h (`_top_news_cache`) :** Indexé par clé `{country}_{language}`, il protège le quota strict de 50 requêtes/jour de WorldNewsAPI tout en évitant toute collision entre les pays sélectionnés.

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

## 6. Authentification, Sécurité Multi-Tenant & Protection FinOps

- **Tokens JWT Stateless :** Signature cryptographique HMAC-SHA256 (`SECRET_KEY` dédiée en production) avec expiration à 24 heures.
- **Chiffrement & Rotation des Identifiants :** Hachage robuste via `bcrypt` avec sel unique (*salt*). En production, les variables `DEMO_USER_EMAIL` et `DEMO_USER_PASSWORD` mettent automatiquement à jour le compte autorisé au démarrage et désactivent le mot de passe local par défaut (`test`), tandis que l'encadré d'auto-connexion est masqué sur le build de production Vercel (`NODE_ENV=production`).
- **Protection Anti-Bruteforce & CORS Restreint :** Limitation automatique des tentatives échouées par IP sur `/login` (`MAX_LOGIN_ATTEMPTS`, rejet `HTTP 429`) et filtrage des origines autorisées via `CORS_ORIGINS`.
- **Plafond Quotidien de Sécurité IA (`MAX_DAILY_AI_CALLS`) :** Garde-fou FinOps applicatif empêchant tout emballement ou consommation abusive des abonnements facturés à l'usage (Google Gemini & WorldNewsAPI) au-delà d'un seuil journalier configurable.
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
1. Recherche d'actualités en direct : Tu as accès à l'outil `search_news`. Utilise-le SYSTÉMATIQUEMENT dès que la question porte sur des événements récents, marchés financiers, faits du jour.
   - Ta query doit être concise : 1 à 3 mots-clés maximum (ex: 'bourse Asie', 'CAC 40', 'Nikkei').
   - Ne mets jamais de longues phrases ou listes de pays.
   - CIBLAGE GÉOGRAPHIQUE ET LINGUISTIQUE DES SOURCES :
     * USA : `language='en'` et `country='us'` (médias américains originaux).
     * Royaume-Uni : `language='en'` et `country='gb'`.
     * Allemagne : `language='de'` et `country='de'`.
     * France : `language='fr'` et `country='fr'`.
     * Rédige toujours ton analyse en français pour le journaliste (sauf demande contraire).
2. Lecture approfondie d'articles : Utilise `get_article_content` dès qu'une analyse détaillée ou citation exacte est demandée.
3. Démarche journalistique : Ton journalistique, objectif, clair et structuré.
4. Formattage Markdown : Structure tes réponses avec soin (titres, listes à puces, éléments clés en gras).
5. CITATION OBLIGATOIRE DES SOURCES AVEC LIENS CLIQUABLES & DÉDUPLICATION : Inclus les liens [Nom du média - Titre](url) et termine par la section `### 📰 Sources consultées` sans aucun doublon.
6. TRANSPARENCE ET VÉRACITÉ (RÈGLE ABSOLUE) : Si aucun article n'est trouvé, indique-le clairement ("Aucun article récent n'a été trouvé..."). Il est formellement interdit d'inventer des citations de presse fictives si tu n'as pas obtenu les articles via search_news.
```

**Justifications des choix :**
1. **Règle de citation systématique et déduplication (Règle 5) :** Dans le journalisme, une information sans source vérifiable est inutilisable. Le prompt force le modèle à mentionner la source et à formater les liens markdown `[Titre](URL)`. En complément, une garantie déterministe applicative (`ensure_sources_section` + `deduplicate_sources_section`) injecte la section et nettoie les doublons si le LLM omet de la retranscrire lors de dialogues longs.
2. **Déclenchement systématique, calibrage des requêtes et ciblage géographique (Règles 1 et 2) :** L'exigence de requêtes courtes (1 à 3 mots-clés) empêche le modèle d'envoyer des phrases entières qui satureraient le moteur de recherche WorldNewsAPI, tandis que le ciblage par pays/langue assure l'exploitation de sources primaires locales plutôt que de dépêches secondaires traduites.
3. **Vérité absolue et interdiction de citations fictives (Règle 6) :** Empêche le modèle d'affirmer « comme le rapportent Reuters ou Bloomberg » s'il n'a pas réellement récupéré les articles récents via ses outils.
4. **Ton et posture déontologique (Règle 3) :** Imposer un ton neutre, factuel et structuré évite les tournures flatteuses ou les jugements de valeur inappropriés pour une rédaction.
5. **Contextualisation dynamique initiale (`/top-news`) :** Lors de la création d'une nouvelle discussion standard, l'API interroge les 3 manchettes françaises phares du jour via WorldNewsAPI et les injecte dans le `system_prompt` de la session (en omettant ce contexte français lorsqu'une enquête internationale spécifique est ouverte). Cela permet à l'assistant d'être immédiatement au fait de l'actualité du jour dès le premier message.

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
| `POST /login` | **401 Unauthorized** | Email inconnu ou mot de passe invalide | `{"detail": "Email ou mot de passe incorrect"}` |
| `POST /login` | **429 Too Many Requests** | Dépassement du seuil anti-bruteforce (`MAX_LOGIN_ATTEMPTS`) | `{"detail": "Trop de tentatives de connexion échouées. Veuillez patienter 15 minutes..."}` |
| `GET /me` | **401 Unauthorized** | Token JWT manquant, invalide ou expiré | `{"detail": "Token d'authentification invalide ou expiré."}` |
| `GET /top-news` | **401 Unauthorized** | Accès aux manchettes sans token JWT valide | `{"detail": "Not authenticated"}` |
| `GET /chats/{id}` | **404 Not Found** | La discussion demandée n'existe pas en BDD | `{"detail": "Discussion non trouvée"}` |
| `GET /chats/{id}` | **403 Forbidden** | La discussion appartient à un autre utilisateur | `{"detail": "Accès interdit : vous n'êtes pas autorisé à consulter cette discussion."}` |
| `PATCH /chats/{id}` | **400 Bad Request** | Le nouveau titre fourni est vide ou constitué uniquement d'espaces | `{"detail": "Le titre de la discussion ne peut pas être vide."}` |
| `PATCH /chats/{id}` | **403 Forbidden** | Tentative de renommage d'une discussion d'un autre utilisateur | `{"detail": "Accès interdit : vous n'êtes pas autorisé à modifier cette discussion."}` |
| `DELETE /chats/{id}` | **403 Forbidden** | Tentative de suppression d'une discussion appartenant à un confrère | `{"detail": "Accès interdit : vous n'êtes pas autorisé à supprimer cette discussion."}` |
| `DELETE /chats/{id}` | **404 Not Found** | Discussion à supprimer introuvable | `{"detail": "Discussion non trouvée"}` |
| `POST /chats/{id}/messages` | **400 Bad Request** | Message vide ou payload JSON malformé | `{"detail": "Le contenu du message ne peut pas être vide."}` |
| `POST /chats/{id}/messages` | **403 Forbidden** | Envoi d'un message sur la discussion d'un autre utilisateur | `{"detail": "Accès interdit : vous n'êtes pas autorisé à modifier cette discussion."}` |
| `POST /chats/{id}/messages` | **402 Payment Required** | Crédits API LLM épuisés (Google AI Studio / prépayé) | `{"detail": "Vos crédits pour l'API Gemini sont épuisés. Veuillez recharger votre solde ou mettre à jour la clé..."}` |
| `POST /chats/{id}/messages` | **429 Too Many Requests** | Dépassement temporaire du quota de requêtes par minute LLM | `{"detail": "Le quota de requêtes par minute de l'API Gemini a été atteint. Veuillez patienter..."}` |
| `POST /chats/{id}/press-review`| **400 Bad Request** | Le thème de revue de presse fourni est vide | `{"detail": "Le thème de la revue de presse ne peut pas être vide."}` |
| `POST /chats/{id}/press-review`| **400 Bad Request** | Tentative de génération sur une discussion vide (sans messages) | `{"detail": "Impossible de générer une revue de presse à partir d'une discussion vide..."}` |
| `POST /chats/{id}/press-review`| **403 Forbidden** | Génération demandée sur une discussion non possédée | `{"detail": "Accès interdit : vous n'êtes pas autorisé à modifier cette discussion."}` |
| `POST /chats/{id}/press-review`| **402 Payment Required** | Crédits API LLM épuisés lors de la synthèse | `{"detail": "Vos crédits pour l'API Gemini sont épuisés..."}` |
| `DELETE /chats/{id}/press-review`| **404 Not Found** | Aucune revue de presse n'existe sur cette discussion | `{"detail": "Aucune revue de presse n'est associée à cette discussion."}` |
| `DELETE /chats/{id}/press-review`| **403 Forbidden** | Tentative de suppression de la revue de presse d'un confrère | `{"detail": "Accès interdit : vous n'êtes pas autorisé à modifier cette discussion."}` |


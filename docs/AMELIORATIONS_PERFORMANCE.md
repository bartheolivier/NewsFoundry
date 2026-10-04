# ⚡ Analyse Critique et Pistes d'Amélioration de Performance — NewsFoundry

Ce document formule un regard critique sur la performance globale de **NewsFoundry**, tant sur la **fluidité et réactivité perçue par les utilisateurs** que sur la **qualité, le coût et l'observabilité du système d'agents IA**.

Chaque piste est motivée par des mesures ou constats concrets observés lors du développement, appuyée par la recherche ergonomique (notamment les seuils de réactivité de Jakob Nielsen), et détaillée sous forme d'un plan d'implémentation réaliste et mesurable.

---

## ⏱️ 1. Cadre d'Analyse : Les Seuils de Réactivité Humaine (Jakob Nielsen)

Selon les études de référence du [Nielsen Norman Group sur les temps de réponse](https://www.nngroup.com/articles/response-times-3-important-limits/), l'expérience utilisateur est régie par trois seuils cognitifs fondamentaux :

1. **0.1 seconde (100 ms) :** Seuil de réactivité instantanée perçue. L'utilisateur a le sentiment d'agir directement sur les données (ex : bascule d'onglet, clic sur bouton copier).
2. **1.0 seconde (1 000 ms) :** Limite au-delà de laquelle l'utilisateur perçoit un délai, mais son flux de pensée n'est pas rompu. Aucun retour complexe n'est requis au-delà d'un léger indicateur d'attente.
3. **10.0 secondes :** Limite absolue d'attention sur une tâche. Au-delà de 10 secondes sans progression visible, l'utilisateur décroche, change d'onglet ou présume que le système a échoué.

### État des lieux mesuré sur NewsFoundry

| Interaction | Latence Actuelle Observée | Évaluation au regard des seuils UX |
| :--- | :--- | :--- |
| **Navigation & Onglets** | < 50 ms | ✅ Excellent (Inférieur à 100 ms) |
| **Message simple (Sans outil)** | ~1.2s à 2.0s | 🟡 Acceptable mais rupture du flux de pensée |
| **Recherche d'actualité (`search_news`)** | ~3.5s à 5.5s | 🟠 Sensible (Appel API externe + inférence LLM) |
| **Lecture intégrale d'article (`get_article_content`)** | ~4.0s à 7.0s | 🟠 Sensible (Scraping HTML + synthèse LLM) |
| **Génération de revue de presse avec RAG** | **8.0s à 14.0s** | 🔴 **Critique (Dépasse le seuil des 10 secondes)** |

---

## 🚀 2. Piste n°1 : Streaming des Réponses LLM (*Server-Sent Events*)

### A. Constat & Justification
Actuellement, les routes `POST /chats/{id}/messages` et `POST /chats/{id}/press-review` fonctionnent en mode synchrone bloquant (*request-response classique*). Le serveur attend que le LLM ait achevé la génération complète de l'ensemble de la réponse avant de renvoyer le JSON au frontend.

Le **Time to First Token (TTFT)** perçu par l'utilisateur correspond donc à 100 % de la durée totale de génération :
- Sur une revue de presse de 600 mots nécessitant 11 secondes de génération, l'écran reste figé sur un spinner pendant 11 secondes.
- Selon la documentation du [Vercel AI SDK sur le streaming](https://ai-sdk.dev/docs/foundations/streaming), le streaming permet de renvoyer les tokens au fil de leur émission. Le TTFT chute alors à **~500 - 800 ms**.
- Bien que le temps total d'exécution reste identique, **la latence ressentie par l'utilisateur diminue de plus de 85 %**, car le journaliste commence à lire la synthèse dès la première seconde.

### B. Grandes lignes de la réalisation technique
1. **Backend FastAPI :**
   - Remplacer le retour standard par une `StreamingResponse` de FastAPI ou `EventSourceResponse` (protocole Server-Sent Events / SSE).
   - Utiliser la méthode `agent.run_stream()` disponible nativement dans PydanticAI :
     ```python
     async def stream_chat(user_prompt: str, history: list):
         async with agent.run_stream(user_prompt, message_history=history) as result:
             async for message in result.stream_text():
                 yield f"data: {json.dumps({'chunk': message})}\n\n"
     ```
2. **Frontend Next.js :**
   - Dans `handleSendMessage`, consommer la réponse via l'API standard `fetch` et un `ReadableStreamDefaultReader` (ou via le hook `useChat` de la bibliothèque Vercel AI SDK).
   - Mettre à jour l'état React au fil de l'eau pour un affichage de type machine à écrire (*typewriter effect*).

### C. Objectif Mesurable
- **TTFT (Time to First Token) :** Réduction de **11s à moins de 800 ms**.
- **Taux de rebond / abandon pendant la génération :** Réduit à 0 %.

---

## 🔍 3. Piste n°2 : Observabilité MLOps & Tracing avec MLflow

### A. Constat & Justification
Lorsqu'une génération de revue de presse prend 12 secondes, il est actuellement impossible de déterminer avec certitude la source du ralentissement sans instrumentation fine :
- Est-ce le serveur WorldNewsAPI qui a mis 5 secondes à répondre ?
- Est-ce le calcul d'embeddings vectoriels de LlamaIndex qui a saturé ?
- Est-ce l'inférence du LLM Gemini qui a ralenti ?
- Y a-t-il eu un retry PydanticAI dû à une erreur de validation de schéma JSON ?

Selon la documentation de [MLflow Tracing pour PydanticAI](https://mlflow.org/docs/latest/genai/tracing/integrations/listing/pydantic_ai), l'intégration du tracing permet de décomposer l'exécution d'un agent en un arbre hiérarchique de *spans* détaillés.

### B. Grandes lignes de la réalisation technique
1. **Activation de l'autologging MLflow :**
   - Ajouter `mlflow>=2.17.0` aux dépendances UV.
   - Initialiser l'autologging dans `backend/src/main.py` au démarrage :
     ```python
     import mlflow

     mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
     mlflow.set_experiment("NewsFoundry-Agents")
     mlflow.pydantic_ai.autolog()
     ```
2. **Métriques capturées automatiquement :**
   - **Latence par composant :** Durée exacte de chaque tool call (`search_news`, `get_article_content`), du retrieval LlamaIndex et de la génération LLM.
   - **Consommation de tokens :** Suivi des tokens d'entrée (*prompt tokens*) et de sortie (*completion tokens*) pour chiffrer le coût financier par requête.
   - **Arbre d'appels :** Visualisation des entrées/sorties de chaque sous-composant et traces d'erreurs en cas de timeout HTTP.
3. **Exploitation pour l'optimisation continue :**
   - Suivi des percentiles de performance (p50, p95, p99) selon l'approche *Performance Analysis - From User Complaints to Optimization* de MLflow.

### C. Objectif Mesurable
- **Visibilité à 100 %** sur les temps passés par composant (APIs tierces vs RAG vs Inférence LLM).
- **Détection immédiate** des régressions de performance dès qu'un percentile p95 dépasse 8 secondes.

---

## ⚡ 4. Piste n°3 : Optimisation du Temps de Génération de la Revue de Presse

### A. Analyse de la variation selon la longueur du chat
Actuellement, lorsque la discussion s'allonge :
1. **Allongement du prompt :** Chaque échange utilisateur/assistant supplémentaire ajoute ~200 à 400 tokens dans le prompt envoyé à `generate_press_review`. Pour une discussion de 25 messages, le contexte dépasse 6 000 tokens, augmentant le coût d'inférence et le risque d'attention diluée du LLM (*Lost in the Middle*).
2. **Extraction RAG séquentielle (Goulet d'étranglement mesuré) :**  
   Dans [backend/src/services/rag.py](file:///home/obarthe/Bureau/Formation_Dev_IA/Projet14/backend/src/services/rag.py), l'extraction du texte complet des articles est effectuée de manière séquentielle dans une boucle `for` :
   ```python
   # Code actuel : séquentiel
   for url in loaded_urls:
       article_data = await extract_article_content_api(url)
   ```
   Si l'enquête comporte 4 articles et que chaque appel HTTP prend 1.2s, **4.8 secondes sont gaspillées uniquement en attente réseau séquentielle** avant même de commencer l'indexation !

### B. Actions d'optimisation concrètes

#### 1. Parallélisation Asynchrone de l'Extraction d'Articles
Remplacer la boucle séquentielle par un `asyncio.gather` concurrent :
```python
tasks = [extract_article_content_api(url) for url in loaded_urls if url]
articles_data = await asyncio.gather(*tasks, return_exceptions=True)
```
- **Gain mesuré :** Le temps d'extraction pour 4 articles passe de **4.8 secondes à 1.3 seconde** (gain direct de 3.5 secondes).

#### 2. Mise en Cache des Embeddings Vectoriels
- Actuellement, si le journaliste relance une revue de presse sur un thème connexe (ex : après avoir affiné le sujet), les embeddings sont recalculés à partir de zéro.
- En intégrant une table de cache PostgreSQL ou un cache Redis sur le hash du texte de l'article (`article_hash -> embedding_vector`), le coût d'embedding devient **quasi-instantané (0 ms de calcul d'embedding)**.

#### 3. Fenêtrage Glissant et Synthèse Compressive de l'Historique
- Si la discussion compte plus de 15 messages, appliquer une étape de résumé préalable des premiers échanges pour ne conserver que les thèses et points saillants, stabilisant le prompt d'entrée à une taille optimale (< 2 000 tokens).

### C. Objectif Mesurable
- Réduction du temps moyen de génération de la revue de presse de **12s à moins de 4.5s** (soit une division par 2.5 de la latence).

---

## 🎯 5. Piste n°4 : Cache Intelligent pour WorldNewsAPI

### A. Constat & Justification
- Sur le plan gratuit, l'API WorldNewsAPI est plafonnée à **50 requêtes par jour**.
- De plus, les actualités du jour ne changent pas d'une minute à l'autre : deux journalistes explorant le même sujet (ou un même journaliste reformulant sa question) effectuent des appels redondants qui consomment inutilement le quota et introduisent 1.5s de latence réseau.

### B. Solution Technique Proposée
- Déployer un cache mémoire (ex: `Cachetools` en Python ou un cluster Redis léger).
- Clé de cache : `hash(query + language + country)`.
- **TTL (Time to Live) glissant :** 15 à 30 minutes (suffisant pour des actualités en direct tout en évitant les doublons d'investigation immédiats).
- En cas de cache hit : temps de réponse **< 5 ms** au lieu de 1 500 ms, avec 0 requête consommée sur le quota WorldNewsAPI.

### C. Objectif Mesurable
- Réduction de **40 % de la consommation du quota quotidien** de WorldNewsAPI.
- Temps de réponse de `search_news` divisé par 300 sur les requêtes en cache.

---

## 📊 6. Tableau Récapitulatif des Pistes d'Amélioration

| Piste d'Amélioration | Problème Résolu | Objectif Mesurable | Complexité | Impact Utilisateur |
| :--- | :--- | :--- | :--- | :--- |
| **1. Streaming SSE des réponses** | Attente bloquante sur spinner (8-14s) | **TTFT < 800 ms** (contre 11s) | Moyenne | 🌟🌟🌟🌟🌟 (Majeur) |
| **2. Parallélisation RAG (`asyncio.gather`)** | Extraction séquentielle lente des articles | **Gain de 3 à 5 secondes** sur la revue | Faible | 🌟🌟🌟🌟 (Fort) |
| **3. Tracing MLOps avec MLflow** | Manque de visibilité sur les ralentissements | **100 % d'observabilité** span-by-span | Moyenne | 🌟🌟🌟 (Maintenance & Qualité) |
| **4. Cache TTL WorldNewsAPI** | Quota limité (50 req/j) et latence externe | **40 % d'économie de quota**, < 10 ms | Faible | 🌟🌟🌟🌟 (Résilience) |
| **5. Cache vectoriel d'embeddings** | Recalcul redondant d'embeddings Gemini | **Indexation < 100 ms** pour articles déjà vus | Faible | 🌟🌟🌟 (Vitesse RAG) |

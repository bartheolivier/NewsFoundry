"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { useAuth } from "@/context/AuthContext";
import styles from "./page.module.css";

interface ArticleSummary {
  title: string;
  source?: string;
  url?: string;
  summary: string;
}

interface PressReviewData {
  title: string;
  topic: string;
  general_summary: string;
  articles: ArticleSummary[];
  perspectives?: string;
  generated_at: string;
}

interface PressReviewItem {
  chat_id: number;
  chat_title: string;
  press_review: PressReviewData;
}

interface ChatSummary {
  id: number;
  user_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  press_review?: PressReviewData | null;
  loaded_articles?: string[];
}

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

interface ChatDetail {
  id: number;
  user_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
  press_review?: PressReviewData | null;
  loaded_articles?: string[];
}

interface TopNewsItem {
  title: string;
  summary: string;
  url?: string;
  publish_date?: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const COUNTRIES = [
  { code: "fr", label: "France", flag: "🇫🇷" },
  { code: "us", label: "USA", flag: "🇺🇸" },
  { code: "gb", label: "UK", flag: "🇬🇧" },
  { code: "de", label: "Allemagne", flag: "🇩🇪" },
];

export default function HomePage() {
  const { user, token, isAuthenticated, isLoading, logout } = useAuth();
  const router = useRouter();

  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChat, setActiveChat] = useState<ChatDetail | null>(null);
  const [inputMessage, setInputMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isEditingTitle, setIsEditingTitle] = useState(false);
  const [editedTitle, setEditedTitle] = useState("");

  // Top News state (Étape 5 & Home)
  const [topNews, setTopNews] = useState<TopNewsItem[]>([]);
  const [selectedCountry, setSelectedCountry] = useState<string>("fr");
  const [isLoadingTopNews, setIsLoadingTopNews] = useState<boolean>(false);

  // Press Review state (Étape 7)
  const [activeTab, setActiveTab] = useState<"chat" | "reviews">("chat");
  const [pressReviews, setPressReviews] = useState<PressReviewItem[]>([]);
  const [isLoadingReviews, setIsLoadingReviews] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [reviewTopic, setReviewTopic] = useState("");
  const [isGeneratingReview, setIsGeneratingReview] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [copiedReviewId, setCopiedReviewId] = useState<number | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Authentication check
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  // Load chats, press reviews and top news on initial mount
  useEffect(() => {
    if (token) {
      loadChats();
      loadPressReviews();
      loadTopNews("fr");
    }
  }, [token]);

  const loadTopNews = async (countryCode: string = selectedCountry) => {
    setIsLoadingTopNews(true);
    try {
      const res = await fetch(`${API_BASE_URL}/top-news?country=${countryCode}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) {
          setTopNews(data);
        }
      }
    } catch {
      // ignore, fallback to default examples
    } finally {
      setIsLoadingTopNews(false);
    }
  };

  const handleCountryChange = (countryCode: string) => {
    if (countryCode === selectedCountry || isLoadingTopNews) return;
    setSelectedCountry(countryCode);
    loadTopNews(countryCode);
  };


  // Scroll to bottom when activeChat messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeChat?.messages, isSending]);

  const loadChats = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/chats`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setChats(data);
      }
    } catch {
      // ignore
    }
  };

  const loadPressReviews = async () => {
    if (!token) return;
    setIsLoadingReviews(true);
    try {
      const res = await fetch(`${API_BASE_URL}/press-reviews`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setPressReviews(data);
      }
    } catch {
      // ignore
    } finally {
      setIsLoadingReviews(false);
    }
  };

  const handleSelectChat = async (chatId: number) => {
    setIsEditingTitle(false);
    setActiveTab("chat");
    setIsLoadingChat(true);
    setErrorMessage(null);
    try {
      const res = await fetch(`${API_BASE_URL}/chats/${chatId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setActiveChat(data);
      } else {
        setErrorMessage("Impossible de charger cette discussion.");
      }
    } catch {
      setErrorMessage("Erreur de connexion au serveur.");
    } finally {
      setIsLoadingChat(false);
    }
  };

  const handleCreateNewChat = async (initialTitle?: string) => {
    setIsEditingTitle(false);
    try {
      const res = await fetch(`${API_BASE_URL}/chats`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title: initialTitle || null }),
      });
      if (res.ok) {
        const newChat = await res.json();
        setActiveChat(newChat);
        await loadChats();
        return newChat.id;
      } else {
        const errData = await res.json().catch(() => ({}));
        setErrorMessage(
          errData.detail || "Erreur lors de la création d'une nouvelle discussion."
        );
      }
    } catch {
      setErrorMessage("Erreur de connexion au serveur lors de la création d'une nouvelle discussion.");
    }
    return null;
  };

  const handleDeleteChat = async (chatId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setIsEditingTitle(false);
    if (!window.confirm("Êtes-vous sûr de vouloir supprimer cette discussion ?")) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/chats/${chatId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        if (activeChat?.id === chatId) {
          setActiveChat(null);
        }
        await loadChats();
      } else {
        setErrorMessage("Impossible de supprimer cette discussion.");
      }
    } catch {
      setErrorMessage("Erreur de connexion au serveur.");
    }
  };

  const handleStartEditingTitle = () => {
    if (!activeChat) return;
    setEditedTitle(activeChat.title);
    setIsEditingTitle(true);
  };

  const handleSaveTitle = async () => {
    if (!activeChat) return;
    const trimmed = editedTitle.trim();
    if (!trimmed) {
      setErrorMessage("Le titre de la discussion ne peut pas être vide.");
      return;
    }
    if (trimmed === activeChat.title) {
      setIsEditingTitle(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/chats/${activeChat.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ title: trimmed }),
      });

      if (res.ok) {
        const updatedChat = await res.json();
        setActiveChat((prev) => (prev ? { ...prev, title: updatedChat.title } : null));
        setChats((prev) =>
          prev.map((c) => (c.id === updatedChat.id ? { ...c, title: updatedChat.title } : c))
        );
        setIsEditingTitle(false);
      } else {
        const err = await res.json().catch(() => ({}));
        setErrorMessage(err.detail || "Erreur lors du renommage de la discussion.");
      }
    } catch {
      setErrorMessage("Impossible de contacter le serveur pour renommer la discussion.");
    }
  };

  const handleCancelEditingTitle = () => {
    setIsEditingTitle(false);
    if (activeChat) {
      setEditedTitle(activeChat.title);
    }
  };


  const handleSendMessage = async (contentToSend?: string) => {
    const text = (contentToSend || inputMessage).trim();
    if (!text || isSending) return;

    setInputMessage("");
    setErrorMessage(null);
    setIsSending(true);

    let currentChatId = activeChat?.id;

    // If no active chat, create one automatically
    if (!currentChatId) {
      // Pick first words for title
      const autoTitle = text.slice(0, 30) + (text.length > 30 ? "..." : "");
      currentChatId = await handleCreateNewChat(autoTitle);
      if (!currentChatId) {
        setIsSending(false);
        return;
      }
    }

    // Optimistically append user message to UI
    const tempUserMsg: Message = {
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    setActiveChat((prev) =>
      prev
        ? { ...prev, messages: [...prev.messages, tempUserMsg] }
        : {
            id: currentChatId!,
            user_id: user?.id || 1,
            title: text.slice(0, 30),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            messages: [tempUserMsg],
          }
    );

    try {
      const res = await fetch(`${API_BASE_URL}/chats/${currentChatId}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ content: text }),
      });

      if (res.ok) {
        const assistantResponse = await res.json();
        setActiveChat((prev) =>
          prev
            ? {
                ...prev,
                messages: [
                  ...prev.messages,
                  {
                    role: "assistant",
                    content: assistantResponse.content,
                    timestamp: assistantResponse.timestamp,
                  },
                ],
                loaded_articles: assistantResponse.loaded_articles || prev.loaded_articles || [],
              }
            : null
        );
        loadChats();
      } else {
        const errData = await res.json().catch(() => ({}));
        setErrorMessage(errData.detail || "Erreur lors de l'envoi du message.");
        // Rollback optimistic message so the conversation stays consistent
        setActiveChat((prev) =>
          prev
            ? {
                ...prev,
                messages: prev.messages.slice(0, -1),
              }
            : null
        );
      }
    } catch {
      setErrorMessage("Impossible de joindre le serveur ou erreur réseau inattendue.");
      setActiveChat((prev) =>
        prev
          ? {
              ...prev,
              messages: prev.messages.slice(0, -1),
            }
          : null
      );
    } finally {
      setIsSending(false);
    }
  };

  const formatTime = (isoString?: string) => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  const formatDate = (isoString?: string) => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString("fr-FR");
    } catch {
      return "";
    }
  };

  const formatLongDate = (isoString?: string) => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString("fr-FR", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  };

  const handleOpenModal = async () => {
    if (!activeChat || activeChat.messages.length === 0) {
      alert("Veuillez d'abord échanger avec l'assistant dans une discussion avant de générer une revue de presse.");
      return;
    }
    const defaultTopic = activeChat.title.startsWith("Discussion du ") ? "" : activeChat.title;
    setReviewTopic(defaultTopic);
    setModalError(null);
    setIsModalOpen(true);

    // Refresh activeChat from server to ensure loaded_articles is 100% synchronized
    try {
      const res = await fetch(`${API_BASE_URL}/chats/${activeChat.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const freshChat = await res.json();
        setActiveChat(freshChat);
      }
    } catch {
      // ignore
    }
  };

  const handleGeneratePressReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeChat) return;
    const topic = reviewTopic.trim();
    if (!topic) {
      setModalError("Veuillez renseigner un thème pour la revue de presse.");
      return;
    }

    setIsGeneratingReview(true);
    setModalError(null);

    try {
      const res = await fetch(`${API_BASE_URL}/chats/${activeChat.id}/press-review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ topic }),
      });

      if (res.ok) {
        const updatedChat = await res.json();
        setActiveChat(updatedChat);
        await loadChats();
        await loadPressReviews();
        setIsModalOpen(false);
        setActiveTab("reviews");
      } else {
        const err = await res.json().catch(() => ({}));
        setModalError(err.detail || "Erreur lors de la génération de la revue de presse.");
      }
    } catch {
      setModalError("Impossible de contacter le serveur.");
    } finally {
      setIsGeneratingReview(false);
    }
  };

  const handleCopyReview = (review: PressReviewItem) => {
    const textToCopy = `**${review.press_review.title}**
Date : ${formatLongDate(review.press_review.generated_at)}
Thème : ${review.press_review.topic}

**Synthèse générale des principales actualités :**
${review.press_review.general_summary}

**Articles et sources analysés :**
${review.press_review.articles
  .map(
    (a) =>
      `• **${a.title}**${a.source ? ` (${a.source})` : ""}${a.url ? ` : ${a.url}` : ""}\n  ${a.summary}`
  )
  .join("\n")}

${review.press_review.perspectives ? `**Perspectives :**\n${review.press_review.perspectives}` : ""}
`;

    navigator.clipboard.writeText(textToCopy);
    setCopiedReviewId(review.chat_id);
    setTimeout(() => {
      setCopiedReviewId(null);
    }, 2000);
  };

  const handleDeletePressReview = async (chatId: number) => {
    if (!window.confirm("Êtes-vous sûr de vouloir supprimer cette revue de presse ?")) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/chats/${chatId}/press-review`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.ok) {
        setPressReviews((prev) => prev.filter((item) => item.chat_id !== chatId));
        if (activeChat?.id === chatId) {
          setActiveChat((prev) => (prev ? { ...prev, press_review: null } : null));
        }
        setChats((prev) =>
          prev.map((c) => (c.id === chatId ? { ...c, press_review: null } : c))
        );
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Impossible de supprimer la revue de presse.");
      }
    } catch {
      alert("Erreur réseau lors de la suppression de la revue de presse.");
    }
  };

  if (isLoading || !isAuthenticated) {
    return (
      <div className={styles.loadingScreen}>
        Chargement de votre espace NewsFoundry...
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* Sidebar */}
      <aside className={styles.sidebar}>
        <div className={styles.sidebarTop}>
          <div className={styles.sidebarHeader}>
            <div className={styles.brand}>
              <span className={styles.brandTitle}>NEWSFOUNDRY</span>
              <span className={styles.brandIcon} aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect width="18" height="14" x="3" y="7" rx="3" />
                  <path d="M12 2v5" />
                  <path d="M9 13h.01" />
                  <path d="M15 13h.01" />
                </svg>
              </span>
            </div>
          </div>

          <button
            type="button"
            className={styles.newChatBtn}
            onClick={() => handleCreateNewChat()}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>Nouvelle discussion</span>
          </button>

          <div className={styles.discussionsList}>
            {chats.length === 0 ? (
              <div className={styles.emptyDiscussions}>
                Aucune discussion pour le moment. Cliquez ci-dessus pour en créer une.
              </div>
            ) : (
              chats.map((chat) => (
                <div
                  key={chat.id}
                  className={`${styles.discussionItem} ${activeChat?.id === chat.id ? styles.discussionItemActive : ""}`}
                  onClick={() => handleSelectChat(chat.id)}
                  role="button"
                  tabIndex={0}
                >
                  <div className={styles.discussionInfo}>
                    <div className={styles.discussionTitle}>{chat.title}</div>
                    <div className={styles.discussionDate}>
                      {formatDate(chat.updated_at)} • {chat.message_count} msg
                    </div>
                  </div>
                  <button
                    type="button"
                    className={styles.deleteChatBtn}
                    onClick={(e) => handleDeleteChat(chat.id, e)}
                    title="Supprimer cette discussion"
                    aria-label="Supprimer cette discussion"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      <line x1="10" y1="11" x2="10" y2="17" />
                      <line x1="14" y1="11" x2="14" y2="17" />
                    </svg>
                  </button>
                </div>
              ))

            )}
          </div>
        </div>

        <div className={styles.sidebarFooter}>
          <button
            type="button"
            className={styles.logoutBtn}
            onClick={logout}
            title="Se déconnecter"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            <span>Se déconnecter ({user?.email})</span>
          </button>
        </div>
      </aside>

      {/* Main Chat Content */}
      <main className={styles.mainContent}>
        {/* Top bar */}
        <header className={styles.topBar}>
          <div className={styles.topBarLeft}>
            <div className={styles.headerNavTabs}>
              <button
                type="button"
                className={`${styles.navTabBtn} ${activeTab === "chat" ? styles.navTabBtnActive : ""}`}
                onClick={() => setActiveTab("chat")}
                title="Accéder au chat"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
                <span>Chat</span>
              </button>
              <button
                type="button"
                className={`${styles.navTabBtn} ${activeTab === "reviews" ? styles.navTabBtnActive : ""}`}
                onClick={() => {
                  setActiveTab("reviews");
                  loadPressReviews();
                }}
                title="Consulter les revues de presse"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
                <span>Revue de presse</span>
              </button>
            </div>

            {activeTab === "chat" && activeChat && (
              <div className={styles.chatTitleContainer} style={{ marginLeft: 8 }}>
                {isEditingTitle ? (
                  <form
                    className={styles.editTitleForm}
                    onSubmit={(e) => {
                      e.preventDefault();
                      handleSaveTitle();
                    }}
                  >
                    <input
                      type="text"
                      className={styles.editTitleInput}
                      value={editedTitle}
                      onChange={(e) => setEditedTitle(e.target.value)}
                      autoFocus
                      maxLength={80}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") handleCancelEditingTitle();
                      }}
                    />
                    <button
                      type="submit"
                      className={styles.saveTitleBtn}
                      title="Enregistrer le titre"
                      aria-label="Enregistrer le titre"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      className={styles.cancelTitleBtn}
                      onClick={handleCancelEditingTitle}
                      title="Annuler"
                      aria-label="Annuler"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </form>
                ) : (
                  <div className={styles.chatTitleRow}>
                    <h2 className={styles.chatTitle}>{activeChat.title}</h2>
                    <button
                      type="button"
                      className={styles.editTitleBtn}
                      onClick={handleStartEditingTitle}
                      title="Renommer la discussion"
                      aria-label="Renommer la discussion"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
                      </svg>
                    </button>
                  </div>
                )}
                <span className={styles.chatSubtitle}>
                  {isEditingTitle ? "Appuyez sur Entrée pour valider, Échap pour annuler" : "Conversation active"}
                </span>
              </div>
            )}
            {activeTab === "chat" && !activeChat && (
              <div className={styles.chatTitleContainer} style={{ marginLeft: 8 }}>
                <h2 className={styles.chatTitle}>Nouvelle discussion</h2>
                <span className={styles.chatSubtitle}>Assistant NewsFoundry</span>
              </div>
            )}
          </div>

          <button
            type="button"
            className={styles.pressReviewBtn}
            onClick={handleOpenModal}
            title="Générer une revue de presse"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
            <span>Générer une revue de presse</span>
          </button>
        </header>

        {/* Tab 1: Chat View */}
        {activeTab === "chat" && (
          <>
            {/* Messages or Welcome View */}
            <div className={styles.messagesContainer}>
              {errorMessage && (
                <div style={{ padding: "10px 14px", backgroundColor: "#fef2f2", color: "#dc2626", borderRadius: 8, fontSize: 13, border: "1px solid #fecaca" }}>
                  {errorMessage}
                </div>
              )}

              {(!activeChat || activeChat.messages.length === 0) && (
                <div className={styles.welcomeCard}>
                  <div className={styles.welcomeIconWrapper}>
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect width="18" height="14" x="3" y="7" rx="3" />
                      <path d="M12 2v5" />
                      <path d="M9 13h.01" />
                      <path d="M15 13h.01" />
                    </svg>
                  </div>

                  <h1 className={styles.welcomeTitle}>Assistant Revue de Presse IA</h1>

                  <p className={styles.welcomeDesc}>
                    Posez-moi des questions sur l'actualité récente ou demandez-moi de préparer une synthèse sur un sujet spécifique.
                  </p>

                  {topNews.length > 0 || isLoadingTopNews ? (
                    <>
                      <div className={styles.topNewsHeader}>
                        <div className={styles.topNewsHeaderLeft}>
                          <span className={styles.topNewsBadge}>⚡ En direct</span>
                          <span>Actualités phares du jour (Breaking News) :</span>
                        </div>
                        <div
                          className={styles.countrySelector}
                          role="group"
                          aria-label="Sélection du pays pour les actualités"
                        >
                          {COUNTRIES.map((c) => (
                            <button
                              key={c.code}
                              type="button"
                              onClick={() => handleCountryChange(c.code)}
                              className={`${styles.countryBtn} ${
                                selectedCountry === c.code ? styles.countryBtnActive : ""
                              }`}
                              title={`Afficher les actualités : ${c.label}`}
                              disabled={isLoadingTopNews && selectedCountry === c.code}
                            >
                              <span>{c.flag}</span>
                              <span className={styles.countryCodeLabel}>{c.code.toUpperCase()}</span>
                            </button>
                          ))}
                        </div>
                      </div>

                      {isLoadingTopNews ? (
                        <div className={styles.topNewsLoading}>
                          <svg
                            className={styles.spinner}
                            width="20"
                            height="20"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                          </svg>
                          <span>
                            Chargement des actualités (
                            {COUNTRIES.find((c) => c.code === selectedCountry)?.label})...
                          </span>
                        </div>
                      ) : (
                        <ul className={styles.topNewsList}>
                          {topNews.slice(0, 3).map((news, idx) => (
                            <li
                              key={idx}
                              className={styles.topNewsItem}
                              onClick={() => {
                                const prompt =
                                  selectedCountry === "us"
                                    ? `Analyse cette actualité américaine (sources US) : "${news.title}"`
                                    : selectedCountry === "gb"
                                    ? `Analyse cette actualité britannique (sources UK) : "${news.title}"`
                                    : selectedCountry === "de"
                                    ? `Analyse cette actualité allemande (sources DE) : "${news.title}"`
                                    : news.title;
                                handleSendMessage(prompt);
                              }}
                              title="Cliquez pour lancer une investigation sur ce sujet"
                            >
                              <div className={styles.topNewsItemTitle}>{news.title}</div>
                              {news.summary && (
                                <div className={styles.topNewsItemSummary}>{news.summary}</div>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                    </>
                  ) : (
                    <>
                      <div className={styles.examplesHeader}>Exemples :</div>
                      <ul className={styles.examplesList}>
                        <li onClick={() => handleSendMessage("Quelles sont les dernières nouvelles en politique ?")}>
                          &ldquo;Quelles sont les dernières nouvelles en politique ?&rdquo;
                        </li>
                        <li onClick={() => handleSendMessage("Génère une revue de presse sur la technologie")}>
                          &ldquo;Génère une revue de presse sur la technologie&rdquo;
                        </li>
                        <li onClick={() => handleSendMessage("Résume l'actualité économique de la semaine")}>
                          &ldquo;Résume l'actualité économique de la semaine&rdquo;
                        </li>
                      </ul>
                    </>
                  )}
                </div>
              )}

              {activeChat &&
                activeChat.messages.map((msg, index) =>
                  msg.role === "user" ? (
                    <div key={index} className={styles.messageRowUser}>
                      <div className={styles.userBubble}>
                        <div>{msg.content}</div>
                        <div className={styles.messageTime}>{formatTime(msg.timestamp)}</div>
                      </div>
                      <div className={styles.userAvatar} aria-hidden="true">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
                          <circle cx="12" cy="7" r="4" />
                        </svg>
                      </div>
                    </div>
                  ) : (
                    <div key={index} className={styles.messageRowAssistant}>
                      <div className={styles.assistantAvatar} aria-hidden="true">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <rect width="18" height="14" x="3" y="7" rx="3" />
                          <path d="M12 2v5" />
                          <path d="M9 13h.01" />
                          <path d="M15 13h.01" />
                        </svg>
                      </div>
                      <div className={styles.assistantBubble}>
                        <div className={styles.markdownContent}>
                          <ReactMarkdown
                            components={{
                              a: ({ ...props }) => (
                                <a
                                  {...props}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                />
                              ),
                            }}
                          >
                            {msg.content}
                          </ReactMarkdown>
                        </div>

                        <div className={styles.assistantTime}>{formatTime(msg.timestamp)}</div>
                      </div>
                    </div>
                  )
                )}

              {isSending && (
                <div className={styles.messageRowAssistant}>
                  <div className={styles.assistantAvatar} aria-hidden="true">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect width="18" height="14" x="3" y="7" rx="3" />
                      <path d="M12 2v5" />
                      <path d="M9 13h.01" />
                      <path d="M15 13h.01" />
                    </svg>
                  </div>
                  <div className={styles.assistantBubble}>
                    <div className={styles.typingIndicator}>
                      <span>L'assistant réfléchit</span>
                      <div className={styles.dotPulse}>
                        <span className={styles.dot}></span>
                        <span className={styles.dot}></span>
                        <span className={styles.dot}></span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Bar */}
            <div className={styles.bottomBar}>
              <form
                className={styles.inputForm}
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendMessage();
                }}
              >
                <input
                  type="text"
                  className={styles.messageInput}
                  placeholder="Posez une question sur l'actualité..."
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  disabled={isSending}
                />
                <button
                  type="submit"
                  className={styles.sendBtn}
                  disabled={isSending || !inputMessage.trim()}
                  aria-label="Envoyer"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </form>
            </div>
          </>
        )}

        {/* Tab 2: Revue de presse View */}
        {activeTab === "reviews" && (
          <div className={styles.reviewsViewContainer}>
            <div className={styles.reviewsHeader}>
              <h1 className={styles.reviewsTitle}>Revues de Presse</h1>
              <p className={styles.reviewsSubtitle}>Consultez et gérez vos revues de presse générées par l'IA</p>
            </div>

            {isLoadingReviews && (
              <div style={{ textAlign: "center", padding: "40px", color: "#6b7280" }}>
                Chargement des revues de presse...
              </div>
            )}

            {!isLoadingReviews && pressReviews.length === 0 && (
              <div className={styles.reviewsEmptyState}>
                <div className={styles.reviewsEmptyIcon}>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" />
                    <line x1="16" y1="17" x2="8" y2="17" />
                    <polyline points="10 9 9 9 8 9" />
                  </svg>
                </div>
                <h3 className={styles.reviewsEmptyTitle}>Aucune revue de presse générée</h3>
                <p className={styles.reviewsEmptyDesc}>
                  Échangez avec l'assistant dans une discussion pour explorer un sujet d'actualité, puis cliquez sur le bouton <strong>« Générer une revue de presse »</strong> en haut à droite.
                </p>
              </div>
            )}

            {!isLoadingReviews && pressReviews.length > 0 && (
              <div className={styles.reviewsList}>
                {pressReviews.map((item) => (
                  <article key={item.chat_id} className={styles.reviewCard}>
                    <div className={styles.reviewCardHeader}>
                      <div className={styles.reviewCardHeaderLeft}>
                        <h2 className={styles.reviewCardTitle}>{item.press_review.title}</h2>
                        <div className={styles.reviewCardDate}>
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <rect width="18" height="18" x="3" y="4" rx="2" ry="2" />
                            <line x1="16" y1="2" x2="16" y2="6" />
                            <line x1="8" y1="2" x2="8" y2="6" />
                            <line x1="3" y1="10" x2="21" y2="10" />
                          </svg>
                          <span>{formatLongDate(item.press_review.generated_at)}</span>
                        </div>
                      </div>

                      <div className={styles.reviewCardActions}>
                        <button
                          type="button"
                          className={`${styles.copyReviewBtn} ${copiedReviewId === item.chat_id ? styles.copyReviewBtnCopied : ""}`}
                          onClick={() => handleCopyReview(item)}
                          title="Copier la revue de presse"
                        >
                          {copiedReviewId === item.chat_id ? (
                            <>
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12" />
                              </svg>
                              <span>Copié !</span>
                            </>
                          ) : (
                            <>
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <rect width="13" height="13" x="9" y="9" rx="2" ry="2" />
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                              </svg>
                              <span>Copier</span>
                            </>
                          )}
                        </button>

                        <button
                          type="button"
                          className={styles.deleteReviewBtn}
                          onClick={() => handleDeletePressReview(item.chat_id)}
                          title="Supprimer cette revue de presse"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="3 6 5 6 21 6" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            <line x1="10" y1="11" x2="10" y2="17" />
                            <line x1="14" y1="11" x2="14" y2="17" />
                          </svg>
                          <span>Supprimer</span>
                        </button>
                      </div>
                    </div>

                    <div className={styles.reviewCardBody}>
                      <div className={styles.reviewThemeTag}>
                        Thème : {item.press_review.topic}
                      </div>

                      <div className={styles.reviewGeneralSummary}>
                        <div style={{ fontWeight: 700, marginBottom: 6, color: "#111827" }}>Synthèse générale des principales actualités :</div>
                        {item.press_review.general_summary}
                      </div>

                      {item.press_review.articles && item.press_review.articles.length > 0 && (
                        <div className={styles.reviewArticlesSection}>
                          <div className={styles.reviewArticlesTitle}>Articles et sources analysés :</div>
                          <ul className={styles.reviewArticlesList}>
                            {item.press_review.articles.map((art, aIdx) => (
                              <li key={aIdx} className={styles.reviewArticleItem}>
                                <span className={styles.reviewArticleTitle}>{art.title}</span>
                                {art.source && <span className={styles.reviewArticleSource}>({art.source})</span>}
                                {art.url && (
                                  <a
                                    href={art.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className={styles.reviewArticleLink}
                                  >
                                    Lien source ↗
                                  </a>
                                )}
                                <div style={{ marginTop: 2 }}>{art.summary}</div>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {item.press_review.perspectives && (
                        <div className={styles.reviewPerspectives}>
                          <strong>Perspectives : </strong>
                          {item.press_review.perspectives}
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Modal Générer une revue de presse */}
      {isModalOpen && (
        <div className={styles.modalOverlay} onClick={() => !isGeneratingReview && setIsModalOpen(false)}>
          <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className={styles.modalCloseBtn}
              onClick={() => !isGeneratingReview && setIsModalOpen(false)}
            >
              Fermer
            </button>

            <h2 className={styles.modalTitle}>Générer une revue de presse</h2>
            <p className={styles.modalSubtitle}>Donner un titre à votre revue de presse</p>

            <form className={styles.modalForm} onSubmit={handleGeneratePressReview}>
              <label htmlFor="reviewTopicInput" className={styles.modalLabel}>
                Thème de la revue de presse
              </label>
              <input
                id="reviewTopicInput"
                type="text"
                className={styles.modalInput}
                value={reviewTopic}
                onChange={(e) => setReviewTopic(e.target.value)}
                placeholder="Ex : Actualités politiques - Semaine 39"
                disabled={isGeneratingReview}
                autoFocus
              />

              {activeChat?.loaded_articles && activeChat.loaded_articles.length > 0 && (
                <div style={{
                  padding: "8px 12px",
                  borderRadius: 6,
                  backgroundColor: "#eff6ff",
                  border: "1px solid #bfdbfe",
                  color: "#1e40af",
                  fontSize: 12,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginTop: -6,
                  marginBottom: 10,
                }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <path d="m9 12 2 2 4-4" />
                  </svg>
                  <span>
                    <strong>Enrichissement RAG actif :</strong> {activeChat.loaded_articles.length} article(s) indexé(s) pour la recherche sémantique.
                  </span>
                </div>
              )}

              {modalError && <div className={styles.modalError}>{modalError}</div>}

              <button
                type="submit"
                className={styles.modalSubmitBtn}
                disabled={isGeneratingReview || !reviewTopic.trim()}
              >
                {isGeneratingReview ? (
                  <>
                    <svg className={styles.spinner} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                    </svg>
                    <span>Génération en cours...</span>
                  </>
                ) : (
                  <span>Générer</span>
                )}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

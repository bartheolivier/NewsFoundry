"use client";

import React, { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import { useAuth } from "@/context/AuthContext";
import styles from "./page.module.css";

interface ChatSummary {
  id: number;
  user_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
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
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function HomePage() {
  const { user, token, isAuthenticated, isLoading, logout } = useAuth();
  const router = useRouter();

  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [activeChat, setActiveChat] = useState<ChatDetail | null>(null);
  const [inputMessage, setInputMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Authentication check
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  // Load chats on initial mount
  useEffect(() => {
    if (token) {
      loadChats();
    }
  }, [token]);

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

  const handleSelectChat = async (chatId: number) => {
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
      }
    } catch {
      setErrorMessage("Erreur lors de la création d'une nouvelle discussion.");
    }
    return null;
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
              }
            : null
        );
        loadChats();
      } else {
        const errData = await res.json().catch(() => ({}));
        setErrorMessage(errData.detail || "Erreur lors de l'envoi du message.");
      }
    } catch {
      setErrorMessage("Impossible de joindre le serveur.");
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
                <button
                  key={chat.id}
                  type="button"
                  className={`${styles.discussionItem} ${activeChat?.id === chat.id ? styles.discussionItemActive : ""}`}
                  onClick={() => handleSelectChat(chat.id)}
                >
                  <div className={styles.discussionTitle}>{chat.title}</div>
                  <div className={styles.discussionDate}>
                    {formatDate(chat.updated_at)} • {chat.message_count} msg
                  </div>
                </button>
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
            {activeChat && (
              <div className={styles.chatTitleContainer}>
                <h2 className={styles.chatTitle}>{activeChat.title}</h2>
                <span className={styles.chatSubtitle}>Conversation active</span>
              </div>
            )}
            {!activeChat && (
              <div className={styles.chatTitleContainer}>
                <h2 className={styles.chatTitle}>Nouvelle discussion</h2>
                <span className={styles.chatSubtitle}>Assistant NewsFoundry</span>
              </div>
            )}
          </div>

          <button
            type="button"
            className={styles.pressReviewBtn}
            onClick={() => alert("La génération de revue de presse sera activée à l'étape 7 !")}
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
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
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
      </main>
    </div>
  );
}

"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import styles from "./page.module.css";

export default function HomePage() {
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<"chat" | "revue">("chat");

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isLoading, router]);

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
        <div>
          <div className={styles.sidebarHeader}>
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

          <div className={styles.discussionsList}>
            <div className={styles.discussionItem}>
              <div className={styles.discussionTitle}>Discussion du</div>
              <div className={styles.discussionDate}>10/12/2026</div>
            </div>
            <div className={styles.discussionItem}>
              <div className={styles.discussionTitle}>Discussion du</div>
              <div className={styles.discussionDate}>10/12/2026</div>
            </div>
          </div>
        </div>

        <div className={styles.sidebarFooter}>
          <button
            type="button"
            className={styles.logoutBtn}
            onClick={logout}
            title="Se déconnecter de votre session"
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

      {/* Main Content Area */}
      <main className={styles.mainContent}>
        {/* Top bar with tabs */}
        <header className={styles.topBar}>
          <div className={styles.tabPillGroup}>
            <button
              type="button"
              className={activeTab === "chat" ? styles.tabPillActive : styles.tabPillInactive}
              onClick={() => setActiveTab("chat")}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              <span>Chat</span>
            </button>
            <button
              type="button"
              className={activeTab === "revue" ? styles.tabPillActive : styles.tabPillInactive}
              onClick={() => setActiveTab("revue")}
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
        </header>

        {/* Central Chat / Welcome Area */}
        <div className={styles.chatArea}>
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
              Posez-moi des questions sur l'actualité récente ou demandez-moi de générer une revue de presse sur un sujet spécifique.
            </p>

            <div className={styles.examplesHeader}>Exemples :</div>
            <ul className={styles.examplesList}>
              <li>&ldquo;Quelles sont les dernières nouvelles en politique ?&rdquo;</li>
              <li>&ldquo;Génère une revue de presse sur la technologie&rdquo;</li>
              <li>&ldquo;Résume l'actualité économique de la semaine&rdquo;</li>
            </ul>
          </div>
        </div>

        {/* Bottom input bar */}
        <div className={styles.bottomBar}>
          <input
            type="text"
            className={styles.messageInput}
            placeholder="Tapez votre message ici..."
            disabled
          />
          <button type="button" className={styles.sendBtn} disabled aria-label="Envoyer le message">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </main>
    </div>
  );
}

"use client"

import { useEffect, useRef, useState } from "react"
import { T } from "@/styles/theme";
import type {
  Product,
  Message,
  SessionEntry,
  BackendResponse,
  CanonicalProduct,
} from "@/types/index";

import {
  QUICKCHIPS,
  STORECOLORS,
  FILTERCOLORS,
} from "@/lib/constants";

import RoboIcon from "@/components/common/RoboIcon";
import StarRating from "@/components/product/StarRating";
import ProductCard from "@/components/product/ProductCard";
import CanonicalProductDetails from "@/components/chat/CanonicalProductDetails";
import ChatCards from "@/components/chat/ChatCards";
import FilterSidebar from "@/components/sidebar/FilterSidebar";
import { filterColor } from "@/lib/filterColor";
import RecentSearchSidebar from "@/components/sidebar/RecentSearchSidebar";
import { useChat } from "@/hooks/useChat";
import { normalizeProducts } from "@/utils/normalizeProducts";
import { motion, AnimatePresence } from "framer-motion";

import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock,
  ExternalLink,
  Plus,
  Search,
  Send,
  ShoppingBag,
  SlidersHorizontal,
  Star,
  X,
  Sparkles,
} from "lucide-react"
import WelcomeScreen from "@/components/WelcomeScreen";

function renderContent(text: string) {
  return text.split("\n").map((line, li) => {
    const parts = line.split(/(\*\*.*?\*\*)/)
    return (
      <div key={li} style={{ minHeight: line ? 6 : undefined }}>
        {parts.map((part, pi) =>
          part.startsWith("**") && part.endsWith("**") ? (
            <strong key={pi} style={{ color: T.accent, fontWeight: 700 }}>
              {part.slice(2, -2)}
            </strong>
          ) : (
            <span key={pi}>{part}</span>
          ),
        )}
      </div>
    )
  })
}

export default function App() {
  const {
    query,
    setQuery,
    messages,
    setMessages,
    isLoading,
    setIsLoading,
    sessionId,
    setSessionId,
    sessions,
    setSessions,
    activeSession,
    setActiveSession,
    recentCollapsed,
    setRecentCollapsed,
    activeProductLabel,
    setActiveProductLabel,
    messagesScrollRef,
    inputRef,
    handleSend,
    handleNewSearch,
    handleScrape,
  } = useChat();

  const isHome = messages.length === 0

  return (
    <div
      style={{
        display: "flex",
        height: "100dvh",
        minHeight: 0,
        color: T.text0,
        fontFamily: T.sans,
        overflow: "hidden",
        position: "relative",
        background: T.bg0,
      }}
    >
      {/* Animated Background Mesh */}
      <div className="bg-gradient-mesh">
        <div className="mesh-blob" style={{ background: T.accent, width: '40vw', height: '40vw', top: '-10%', left: '-10%' }} />
        <div className="mesh-blob" style={{ background: T.indigo, width: '35vw', height: '35vw', bottom: '-5%', right: '-5%', animationDelay: '-5s' }} />
        <div className="mesh-blob" style={{ background: T.pink, width: '30vw', height: '30vw', top: '20%', right: '10%', animationDelay: '-10s' }} />
      </div>

      {sessions.length > 0 && (
        <RecentSearchSidebar
          collapsed={recentCollapsed}
          onToggle={() => setRecentCollapsed((v) => !v)}
          sessions={sessions}
          activeSession={activeSession}
          onSelect={(s) => {
            setMessages(s.messages);
            setActiveSession(s.query);
            setActiveProductLabel(s.query);
          }}
        />
      )}

      <main
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          minWidth: 0,
          position: "relative",
          zIndex: 1,
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "14px 24px",
            borderBottom: `1px solid ${T.border}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
            background: "rgba(13, 13, 13, 0.7)",
            backdropFilter: "blur(20px)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <motion.div
              animate={{ 
                boxShadow: ["0 0 0px #3B82F6", "0 0 15px #3B82F6", "0 0 0px #3B82F6"]
              }}
              transition={{ duration: 2, repeat: Infinity }}
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: T.accent,
              }}
            />
            <span style={{ fontSize: 14, fontWeight: 800, color: T.text0, fontFamily: T.display, letterSpacing: '0.5px' }}>
              {activeProductLabel || activeSession || "OTTIXHOW BOT"}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleNewSearch}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "8px 16px",
                borderRadius: 12,
                border: `1px solid ${T.border}`,
                background: "rgba(255, 255, 255, 0.05)",
                color: T.text0,
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.2s",
              }}
            >
              <Plus size={14} />
              New Chat
            </motion.button>
          </div>
        </div>

        {isHome ? (
          <WelcomeScreen handleSend={handleSend} />
        ) : (
          <div
            ref={messagesScrollRef}
            style={{
              flex: 1,
              minHeight: 0,
              overflowY: "auto",
              padding: "32px 24px",
              display: "flex",
              flexDirection: "column",
              gap: 24,
            }}
          >
            <AnimatePresence initial={false}>
              {messages.map((msg, i) => (
                <motion.div 
                  key={i}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4 }}
                  style={{ display: "flex", flexDirection: "column" }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                      alignItems: "flex-start",
                      gap: 12,
                    }}
                  >
                    {msg.role === "assistant" && (
                      <div style={{ flexShrink: 0, marginTop: 4 }}>
                        <RoboIcon size={32} />
                      </div>
                    )}
                    <div
                      style={{
                        maxWidth: "80%",
                        borderRadius: msg.role === "user" ? "20px 20px 4px 20px" : "4px 20px 20px 20px",
                        background: msg.role === "user"
                            ? `linear-gradient(135deg, ${T.accent}, ${T.indigo})`
                            : "rgba(255, 255, 255, 0.05)",
                        border: msg.role === "user" ? "none" : `1px solid ${T.border}`,
                        padding: "14px 20px",
                        fontSize: 15,
                        lineHeight: 1.6,
                        color: "#fff",
                        boxShadow: msg.role === "user" ? "0 10px 20px rgba(59, 130, 246, 0.2)" : "none",
                      }}
                    >
                      {renderContent(msg.content)}
                    </div>
                  </div>

                  {msg.role === "assistant" && msg.products && msg.products.length > 0 && (
                    <motion.div 
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      style={{ marginTop: 16, marginLeft: 44 }}
                    >
                      <div style={{ display: "flex", gap: 16, overflowX: "auto", paddingBottom: 12 }}>
                        {msg.products.map((product, pi) => (
                          <ProductCard key={pi} product={product} />
                        ))}
                      </div>
                    </motion.div>
                  )}

                  {msg.role === "assistant" && msg.canonicalProduct && (
                    <div style={{ marginLeft: 44, marginTop: 16 }}>
                      <CanonicalProductDetails
                        data={msg.canonicalProduct}
                        searchQuery={msg.parsedSearchQuery}
                        isSearching={isLoading}
                        onSearch={() => {
                          if (msg.canonicalProduct && msg.parsedSearchQuery) {
                            void handleScrape(msg.parsedSearchQuery, msg.canonicalProduct)
                          }
                        }}
                      />
                    </div>
                  )}

                  {msg.role === "assistant" && msg.cards && msg.cards.length > 0 && (
                    <div style={{ marginLeft: 44, marginTop: 16 }}>
                      <ChatCards
                        cards={msg.cards}
                        onOptionSelect={(text) => {
                          if (msg.optionUsed) return
                          void handleSend(text)
                        }}
                      />
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {isLoading && (
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                style={{ display: "flex", alignItems: "center", gap: 12 }}
              >
                <RoboIcon size={32} />
                <div style={{
                  padding: "12px 20px",
                  borderRadius: "4px 20px 20px 20px",
                  background: "rgba(255, 255, 255, 0.05)",
                  border: `1px solid ${T.border}`,
                  display: "flex",
                  gap: 6
                }}>
                  {[0, 1, 2].map((j) => (
                    <motion.div
                      key={j}
                      animate={{ scale: [1, 1.5, 1], opacity: [0.3, 1, 0.3] }}
                      transition={{ duration: 1, repeat: Infinity, delay: j * 0.2 }}
                      style={{ width: 6, height: 6, borderRadius: "50%", background: T.accent }}
                    />
                  ))}
                </div>
              </motion.div>
            )}
          </div>
        )}

        {/* Input Area */}
        <div
          style={{
            padding: "20px 24px 32px",
            background: "transparent",
            position: "relative",
            zIndex: 2,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              background: "rgba(20, 20, 20, 0.8)",
              backdropFilter: "blur(20px)",
              border: `1px solid ${T.border}`,
              borderRadius: 24,
              padding: "8px 8px 8px 24px",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.4)",
              maxWidth: 900,
              margin: "0 auto",
            }}
          >
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleSend()}
              placeholder="Ask anything about products..."
              disabled={isLoading}
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                outline: "none",
                color: "#fff",
                fontSize: 15,
                fontFamily: T.sans,
              }}
            />
            <motion.button
              whileHover={{ scale: 1.05, boxShadow: "0 0 20px rgba(59, 130, 246, 0.4)" }}
              whileTap={{ scale: 0.95 }}
              onClick={() => void handleSend()}
              disabled={!query.trim() || isLoading}
              style={{
                width: 48,
                height: 48,
                borderRadius: 18,
                background: query.trim() && !isLoading ? `linear-gradient(135deg, ${T.accent}, ${T.indigo})` : "rgba(255, 255, 255, 0.05)",
                border: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: query.trim() && !isLoading ? "pointer" : "default",
                transition: "all 0.2s",
              }}
            >
              <Send size={20} color="#fff" />
            </motion.button>
          </div>
        </div>
      </main>

      <style>{`
        input::placeholder { color: rgba(255, 255, 255, 0.3); }
      `}</style>
    </div>
  )
}
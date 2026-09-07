"use client"

import { AnimatePresence, motion } from "framer-motion"
import { useEffect, useState } from "react"
import {
  Bell,
  Grid2X2,
  Heart,
  History,
  Home as HomeIcon,
  Lightbulb,
  Moon,
  Plus,
  Scale,
  Send,
  Sparkles,
  Sun,
  Tag,
  UserRound,
} from "lucide-react"

import WelcomeScreen from "@/components/WelcomeScreen"
import CanonicalProductDetails from "@/components/chat/CanonicalProductDetails"
import ChatCards from "@/components/chat/ChatCards"
import ProductCard from "@/components/product/ProductCard"
import RoboIcon from "@/components/common/RoboIcon"
import { useChat } from "@/hooks/useChat"
import { addWishlist, createPriceAlert, deletePriceAlert, listPriceAlerts, listWishlist, removeWishlist } from "@/services/api"
import type { PriceAlert } from "@/services/api"
import type { Message, Product } from "@/types"

const navItems = [
  { label: "Home", icon: HomeIcon },
  { label: "Deals", icon: Tag },
  { label: "Categories", icon: Grid2X2 },
  { label: "Compare", icon: Scale },
  { label: "My Searches", icon: History },
  { label: "Price Alerts", icon: Bell },
  { label: "Wishlist", icon: Heart },
]

const trySuggestions = [
  "Best camera phone under 30K",
  "Laptop for gaming under 60K",
  "Noise cancelling headphones",
  "Air purifier under 20K",
]

function renderContent(text: string) {
  return text.split("\n").map((line, lineIndex) => {
    const parts = line.split(/(\*\*.*?\*\*)/)
    return (
      <div key={lineIndex} style={{ minHeight: line ? 6 : undefined }}>
        {parts.map((part, partIndex) => part.startsWith("**") && part.endsWith("**") ? <strong key={partIndex}>{part.slice(2, -2)}</strong> : <span key={partIndex}>{part}</span>)}
      </div>
    )
  })
}

function LoadingIndicator({ title, description, tip, stage }: { title?: string; description?: string; tip?: string; stage?: number }) {
  if (!title && !description && !tip) return null
  const stages = ["", "Searching Amazon...", "Searching Flipkart...", "Comparing prices and features...", "Preparing recommendations..."]
  return (
    <motion.div className="chat-message-row" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <div className="ai-avatar"><RoboIcon size={34} /></div>
      <div className="message-bubble">
        {title && <div style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 800 }}>{title}<span className="loading-orb" /></div>}
        {description && <div>{description}</div>}
        {stage != null && stage > 0 && stage < stages.length && <div style={{ color: "#797e94", marginTop: 5 }}>{stages[stage]}</div>}
        {tip && <div className="loading-tip"><Lightbulb size={14} />{tip}</div>}
      </div>
    </motion.div>
  )
}

export default function App() {
  const {
    query, setQuery, messages, setMessages, isLoading, loadingContent, loadingStage,
    sessionId, sessions, activeSession, setActiveSession, setActiveProductLabel,
    messagesScrollRef, inputRef, handleSend, handleFilterSearch, handleProductAction,
    handleNewSearch, handleScrape,
  } = useChat()

  const [isDark, setIsDark] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [wishlistKeys, setWishlistKeys] = useState<string[]>([])
  const [wishlistItems, setWishlistItems] = useState<Array<{ id: number; product: Record<string, unknown> }>>([])
  const [alerts, setAlerts] = useState<PriceAlert[]>([])
  const [activeSection, setActiveSection] = useState("Home")
  const isHome = messages.length === 0

  useEffect(() => {
    const timer = window.setTimeout(() => setIsDark(window.localStorage.getItem("shoppingmind-theme") === "dark"), 0)
    return () => window.clearTimeout(timer)
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        const saved = JSON.parse(window.localStorage.getItem("shoppingmind-wishlist") || "[]")
        if (Array.isArray(saved)) setWishlistKeys(saved.filter((value): value is string => typeof value === "string"))
      } catch {
        setWishlistKeys([])
      }
      void listWishlist(sessionId).then((result) => setWishlistItems(result.items || [])).catch(() => undefined)
      void listPriceAlerts(sessionId).then((result) => setAlerts(result.alerts || [])).catch(() => undefined)
    }, 0)
    return () => window.clearTimeout(timer)
  }, [sessionId])

  const toggleTheme = () => {
    setIsDark((value) => {
      const nextValue = !value
      window.localStorage.setItem("shoppingmind-theme", nextValue ? "dark" : "light")
      return nextValue
    })
  }

  const wishlistKey = (product: Product) => `${product.store || ""}:${product.productlink || product.url || product.productname || product.title || ""}`

  const toggleWishlist = (product: Product) => {
    const key = wishlistKey(product)
    const existing = wishlistItems.find((item) => wishlistKey(item.product as Product) === key)
    const next = wishlistKeys.includes(key) ? wishlistKeys.filter((item) => item !== key) : [...wishlistKeys, key]
    setWishlistKeys(next)
    window.localStorage.setItem("shoppingmind-wishlist", JSON.stringify(next))
    void (existing ? removeWishlist(sessionId, existing.id) : addWishlist(sessionId, product as unknown as Record<string, unknown>))
      .then(() => listWishlist(sessionId).then((result) => setWishlistItems(result.items || [])))
      .catch(() => undefined)
  }

  const navigateTo = (label: string) => {
    setActiveSection(label)
    if (label === "Home") {
      if (!isHome) void handleNewSearch()
      return
    }
    if (label === "My Searches" || label === "Price Alerts" || label === "Wishlist") {
      setActiveProductLabel(label)
      return
    }
    const prompts: Record<string, string> = {
      Deals: "Show me today's best deals",
      Categories: "Show me popular shopping categories",
      Compare: "Compare the best products for me",
      "Price Alerts": "Help me set a price alert",
      Wishlist: "Show my shopping wishlist",
    }
    if (prompts[label]) void handleSend(prompts[label])
  }

  return (
    <div className={`dashboard-shell ${isDark ? "theme-dark" : "theme-light"}`}>
      <header className="global-header">
        <div className="global-brand">
          <div className="brand-mark"><ShoppingBagIcon /></div>
          <strong>OTTIXHOW <span>BOT</span></strong>
        </div>
        <nav className="top-nav" aria-label="Primary navigation">
          {navItems.slice(0, 5).map(({ label }) => <button type="button" key={label} className={label === activeSection ? "active" : ""} onClick={() => navigateTo(label)}>{label}</button>)}
        </nav>
        <div className="topbar-actions">
          <button type="button" className="new-chat-btn" onClick={handleNewSearch}><Plus /><span>New Chat</span></button>
          <div className="profile-wrap"><button type="button" className="profile-button" aria-label="Open profile" aria-expanded={profileOpen} onClick={() => setProfileOpen((value) => !value)}><UserRound size={21} /></button>{profileOpen && <div className="profile-menu"><strong>Shopping profile</strong><span>Wishlist items: {wishlistKeys.length}</span><span>Sessions: {sessions.length}</span></div>}</div>
        </div>
      </header>

      <div className="dashboard-layout">
        <aside className="app-sidebar" aria-label="Sidebar navigation">
          <nav className="sidebar-nav">
            {navItems.map(({ label, icon: Icon }) => <button type="button" key={label} className={label === activeSection ? "active" : ""} onClick={() => navigateTo(label)}><Icon /><span>{label}</span></button>)}
          </nav>

          {sessions.length > 0 && <div className="sidebar-history">
            {sessions.slice(0, 3).map((session) => <button type="button" key={session.query} className={activeSession === session.query ? "selected" : ""} onClick={() => { setMessages(session.messages); setActiveSession(session.query); setActiveProductLabel(session.query) }} title={session.query}><History size={14} /><span>{session.query}</span></button>)}
          </div>}

          <div className="sidebar-promo">
            <div className="promo-icon"><GemIcon /></div>
            <h3>Best Deals,<br />Everyday!</h3>
            <p>Let our AI find the<br />best for you.</p>
            <button type="button" className="promo-button" onClick={() => void handleSend("Show me today's best deals")}>Explore Deals</button>
          </div>
          <div className="sidebar-mode"><Sun className={isDark ? "dimmed" : "active-mode"} /><button type="button" className={`mode-toggle ${isDark ? "is-dark" : ""}`} aria-label={`Switch to ${isDark ? "light" : "dark"} theme`} aria-pressed={isDark} onClick={toggleTheme}><span /></button><Moon className={isDark ? "active-mode" : "dimmed"} /></div>
        </aside>

        <main className={`dashboard-main ${isHome && activeSection === "Home" ? "dashboard-home" : ""}`}>
          {isHome ? <>
            {activeSection === "My Searches" ? <SearchesPanel sessions={sessions} onSelect={(session) => { setMessages(session.messages); setActiveSession(session.query); setActiveProductLabel(session.query); setActiveSection("Home") }} /> : activeSection === "Wishlist" ? <WishlistPanel items={wishlistItems} /> : activeSection === "Price Alerts" ? <AlertsPanel alerts={alerts} sessionId={sessionId} onCreated={(alert) => setAlerts((current) => [alert, ...current])} onDeleted={(id) => { void deletePriceAlert(sessionId, id); setAlerts((current) => current.filter((alert) => alert.id !== id)) }} /> : <WelcomeScreen handleSend={(text) => void handleSend(text)} />}
            {activeSection === "Home" && <ChatLauncher query={query} setQuery={setQuery} inputRef={inputRef} isLoading={isLoading} handleSend={handleSend} showSuggestions />}
          </> : <div className="chat-view">
            <div ref={messagesScrollRef} className="chat-messages">
              <AnimatePresence initial={false}>
                {messages.map((msg: Message, index: number) => <motion.div key={`${index}-${msg.role}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .25 }}>
                  <div className={`chat-message-row ${msg.role === "user" ? "user" : ""}`}>
                    {msg.role === "assistant" && <div className="ai-avatar"><RoboIcon size={34} /></div>}
                    <div className="message-bubble">{renderContent(msg.content)}</div>
                  </div>
                  {msg.role === "assistant" && msg.products && msg.products.length > 0 && <>
                    <div className="message-products">{msg.products.map((product, productIndex) => <ProductCard key={productIndex} product={product} onWishlist={toggleWishlist} isWishlisted={wishlistKeys.includes(wishlistKey(product))} />)}</div>
                    <div className="message-card-actions">{["compare", "cheapest", "rated", "delivery"].map((action) => <button type="button" key={action} onClick={() => handleProductAction(msg.products!, action as "compare" | "cheapest" | "rated" | "delivery")}>{action === "compare" ? "Compare products" : action === "cheapest" ? "Cheapest option" : action === "rated" ? "Best rated" : "Delivery details"}</button>)}</div>
                  </>}
                  {msg.role === "assistant" && msg.canonicalProduct && <div className="chat-extra-card"><CanonicalProductDetails data={msg.canonicalProduct} searchQuery={msg.parsedSearchQuery} isSearching={isLoading} onSearch={() => msg.canonicalProduct && msg.parsedSearchQuery && void handleScrape(msg.parsedSearchQuery, msg.canonicalProduct, msg.loading)} /></div>}
                  {msg.role === "assistant" && msg.cards && msg.cards.length > 0 && <div className="chat-extra-card"><ChatCards cards={msg.cards} onFilterSubmit={(text, filters) => { if (!msg.optionUsed) void handleFilterSearch(text, filters) }} /></div>}
                </motion.div>)}
              </AnimatePresence>
              {isLoading && <LoadingIndicator title={loadingContent?.title} description={loadingContent?.description} tip={loadingContent?.tip} stage={loadingStage} />}
            </div>
            <ChatLauncher query={query} setQuery={setQuery} inputRef={inputRef} isLoading={isLoading} handleSend={handleSend} />
          </div>}
        </main>
      </div>
    </div>
  )
}

function ChatLauncher({ query, setQuery, inputRef, isLoading, handleSend, showSuggestions = false }: { query: string; setQuery: (value: string) => void; inputRef: React.RefObject<HTMLInputElement | null>; isLoading: boolean; handleSend: () => Promise<void>; showSuggestions?: boolean }) {
  return <div className="chat-launcher">
    <form className="chat-input-shell" onSubmit={(event) => { event.preventDefault(); void handleSend() }}>
      <div className="chat-spark"><Sparkles /></div>
      <input ref={inputRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ask anything about products..." disabled={isLoading} aria-label="Ask about products" />
      <button type="submit" className="send-button" disabled={!query.trim() || isLoading} aria-label="Send message"><Send size={18} /></button>
    </form>
    {showSuggestions && <div className="try-row"><strong>Try asking:</strong>{trySuggestions.map((suggestion) => <button type="button" className="try-chip" key={suggestion} onClick={() => setQuery(suggestion)}>{suggestion}</button>)}</div>}
  </div>
}

function SearchesPanel({ sessions, onSelect }: { sessions: Array<{ query: string; messages: Message[] }>; onSelect: (session: { query: string; messages: Message[] }) => void }) {
  return <section className="dashboard-panel"><div className="panel-heading"><History size={20} /><div><h2>My Searches</h2><p>Open a previous shopping conversation.</p></div></div>{sessions.length === 0 ? <p className="panel-empty">Your completed searches will appear here.</p> : <div className="panel-list">{sessions.map((session) => <button type="button" className="panel-list-item" key={session.query} onClick={() => onSelect(session)}><History size={16} /><span>{session.query}</span><span className="panel-list-count">{session.messages.length} messages</span></button>)}</div>}</section>
}

function WishlistPanel({ items }: { items: Array<{ id: number; product: Record<string, unknown> }> }) {
  return <section className="dashboard-panel"><div className="panel-heading"><Heart size={20} /><div><h2>Wishlist</h2><p>Products you saved from real search results.</p></div></div>{items.length === 0 ? <p className="panel-empty">Save a product with the heart button to see it here.</p> : <div className="panel-list">{items.map((item) => { const product = item.product; const title = String(product.productname || product.title || "Saved product"); const link = String(product.productlink || product.url || ""); return <a className="panel-list-item" key={item.id} href={link || undefined} target={link ? "_blank" : undefined} rel="noreferrer"><Heart size={16} fill="currentColor" /><span>{title}</span><span className="panel-list-count">{product.store ? String(product.store) : "Saved"}</span></a> })}</div>}</section>
}

function AlertsPanel({ alerts, sessionId, onCreated, onDeleted }: { alerts: PriceAlert[]; sessionId: string; onCreated: (alert: PriceAlert) => void; onDeleted: (id: number) => void }) {
  const [searchQuery, setSearchQuery] = useState("")
  const [targetPrice, setTargetPrice] = useState("")
  const [saving, setSaving] = useState(false)
  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!searchQuery.trim() || saving) return
    setSaving(true)
    try {
      const result = await createPriceAlert(sessionId, searchQuery.trim(), targetPrice ? Number(targetPrice) : undefined)
      onCreated(result.alert)
      setSearchQuery("")
      setTargetPrice("")
    } finally { setSaving(false) }
  }
  return <section className="dashboard-panel"><div className="panel-heading"><Bell size={20} /><div><h2>Price Alerts</h2><p>Track a product query and target price.</p></div></div><form className="alert-form" onSubmit={submit}><input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Product to monitor" aria-label="Product to monitor" /><input value={targetPrice} onChange={(event) => setTargetPrice(event.target.value)} type="number" min="1" placeholder="Target ₹" aria-label="Target price" /><button type="submit" disabled={saving || !searchQuery.trim()}>{saving ? "Saving..." : "Create alert"}</button></form>{alerts.length === 0 ? <p className="panel-empty">No active alerts yet.</p> : <div className="panel-list">{alerts.map((alert) => <div className="panel-list-item" key={alert.id}><Bell size={16} /><span>{alert.search_query}{alert.target_price ? ` under ₹${alert.target_price.toLocaleString("en-IN")}` : ""}</span><button type="button" className="panel-delete" onClick={() => onDeleted(alert.id)}>Remove</button></div>)}</div>}</section>
}

function ShoppingBagIcon() {
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M5 8h14l-1 12H6L5 8Z" /><path d="M9 9V6a3 3 0 0 1 6 0v3" /><path d="M9 13h.01M15 13h.01" /></svg>
}

function GemIcon() {
  return <svg width="32" height="32" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.55" strokeLinecap="round" strokeLinejoin="round"><path d="m6 11 4-5h12l4 5-10 13L6 11Z" /><path d="M6 11h20M10 6l6 18 6-18M9 11l7 3 7-3" /></svg>
}

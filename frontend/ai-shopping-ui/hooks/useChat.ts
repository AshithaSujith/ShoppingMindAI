import { useEffect, useRef, useState } from "react";

import type {
  Message,
  SessionEntry,
  Product,
  BackendResponse,
  CanonicalProduct,
} from "@/types";

import { scrapeProducts } from "@/services/api";
export function useChat() {
  const [query, setQuery] = useState("")
  // Full chat transcript for the active session.
  const [messages, setMessages] = useState<Message[]>([])
  // Whether a backend request is currently in flight (disables input, shows typing indicator).
  const [isLoading, setIsLoading] = useState(false)
  // Backend session identifier; regenerated whenever the user starts a new search,
  // so the backend's conversational state resets cleanly.
  const [sessionId, setSessionId] = useState(() => `session_${Date.now()}`)
  // List of recent search sessions shown in the left sidebar (most recent first, capped at 9).
  const [sessions, setSessions] = useState<SessionEntry[]>([])
  // The query string of whichever session is currently active/displayed.
  const [activeSession, setActiveSession] = useState<string | null>(null)
  // Collapsed/expanded state for the right filter sidebar.
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  // Collapsed/expanded state for the left recent-searches sidebar.
  const [recentCollapsed, setRecentCollapsed] = useState(false)
  // The resolved product/search label shown in the top header bar.
  const [activeProductLabel, setActiveProductLabel] = useState<string | null>(null)
  const messagesScrollRef = useRef<HTMLDivElement>(null)

  // Ref to the main text input, used to refocus it after starting a new search.
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const container = messagesScrollRef.current
    if (!container) return

    container.scrollTo({
      top: container.scrollHeight,
      behavior: "smooth",
    })
  }, [messages, isLoading])

  useEffect(() => {
    if (!activeSession || messages.length === 0) return
    setSessions((prev) =>
      prev.map((s) => (s.query === activeSession ? { ...s, messages } : s)),
    )
  }, [messages, activeSession])

  const normalizeProducts = (rawProducts: Record<string, unknown>[]): Product[] =>
    rawProducts.map((p) => ({
      ...(p as Record<string, unknown>),
      priceinr: (p as any).priceinr ?? (p as any).price_inr,
      originalprice: (p as any).originalprice ?? (p as any).original_price,
      discountpercent: (p as any).discountpercent ?? (p as any).discount_percent,
      productname: (p as any).productname ?? (p as any).product_name,
      productlink: (p as any).productlink ?? (p as any).product_link,
      reviewcount: (p as any).reviewcount ?? (p as any).review_count,
      deliverylabel: (p as any).deliverylabel ?? (p as any).delivery_label,
      isbestprice: (p as any).isbestprice ?? (p as any).is_best_price,
      isreliable: (p as any).isreliable ?? (p as any).is_reliable,
    }))

  const handleSend = async (overrideQuery?: string) => {
    const text = overrideQuery ?? query.trim()
    if (!text || isLoading) return

    // A "new session" starts whenever the chat is currently empty (i.e. this is
    // the very first query of a fresh conversation).
    const isNewSession = messages.length === 0

    // Freeze any previously-shown clarification option buttons so they can't be clicked again.
    setMessages((prev) => prev.map((m) => (m.role === "assistant" && m.options && !m.optionUsed ? { ...m, optionUsed: true } : m)))

    if (isNewSession) {
      setActiveSession(text)
      setActiveProductLabel(text)
      // Add this as a new recent-search entry, de-duping by case-insensitive query match
      // and capping the list at 9 entries (most recent first).
      setSessions((prev) => {
        const filtered = prev.filter((s) => s.query.toLowerCase() !== text.toLowerCase())
        return [{ query: text, messages: [], filters: {} }, ...filtered.slice(0, 8)]
      })
    }

    // Optimistically append the user's message, then clear the input and show the loading indicator.
    setMessages((prev) => [...prev, { role: "user", content: text }])
    setQuery("")
    setIsLoading(true)

    try {
      const response = await fetch("http://127.0.0.1:8000/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, session_id: sessionId }),
      })

      const data: BackendResponse = await response.json()
      const responseData = data?.data
      // Backend may indicate the response "type" either via data.type or a top-level message field.
      const type = responseData?.type || data?.message

      if (type === "parsed_query") {
        // Backend has parsed the query into a canonical product + filters,
        // but hasn't scraped yet — show the "Extracted details" panel and
        // a "Search Products" button to trigger scraping.
        const canonicalProduct = responseData?.canonical_product
        const searchQuery = responseData?.search_query || text

        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: responseData?.message || responseData?.assistant_message || "Perfect! I understood your request.",
            canonicalProduct,
            parsedSearchQuery: searchQuery,
          },
        ])
        if (searchQuery) setActiveProductLabel(searchQuery)
      } else if (type === "conversation") {
        // Backend is driving the chat conversationally — questions, quick-reply chips,
        // recommendations, and/or comparisons all ride along on the same message.
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: responseData?.message || responseData?.assistant_message || "",
            questions: responseData?.questions || [],
            chips: responseData?.chips || [],
            recommendations: responseData?.recommendations || [],
            comparison: responseData?.comparison,
            productLine: responseData?.product_line,
            confidence: responseData?.confidence,
            filters: responseData?.filters || {},
            nextAction: responseData?.next_action,
            cards: responseData?.cards || [],
          },
        ])
      } else if (type === "results") {
        // Backend has already produced final results conversationally (no separate
        // scrape round-trip needed) — render products plus any follow-up prompts.
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: responseData?.message || responseData?.assistant_message || "Here are the products I found.",
            products: normalizeProducts(responseData?.products || []),
            followUps: responseData?.follow_ups || [],
          },
        ])
      } else if (type === "products") {
        // Backend has finished scraping — normalize and render the product cards.
        // The backend now owns the recommendation copy, so we just display its message.
        const products = normalizeProducts(responseData?.products || [])
        const searchQuery = responseData?.search_query || text
        if (searchQuery) setActiveProductLabel(searchQuery)

        if (products.length === 0) {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: `No products found for ${searchQuery}. Try rephrasing or a different product.`,
            },
          ])
        } else {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: responseData?.message || responseData?.assistant_message || `Here are the best prices I found for ${searchQuery}.`,
              products,
              searchQuery,
            },
          ])
        }
      } else {
        // Fallback: unknown/unspecified response type — just show whatever message text exists.
        const message = responseData?.message || responseData?.assistant_message || data?.message || "No response."
        setMessages((prev) => [...prev, { role: "assistant", content: message, cards: responseData?.cards || [] }])
      }
    } catch {
      // Network/parsing failure — surface a friendly error instead of crashing.
      setMessages((prev) => [...prev, { role: "assistant", content: "Unable to connect to backend. Please check if the server is running." }])
    } finally {
      setIsLoading(false)
    }
  }
  const handleNewSearch = async () => {
      try {
        await fetch("http://127.0.0.1:8000/session/clear", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId }),
        })
      } catch (err) {
        console.error("Session clear failed:", err)
      }

      // New session ID includes a random suffix to avoid any timestamp collisions.
      setSessionId(`session_${Date.now()}_${Math.random().toString(36).slice(2)}`)
      setMessages([])
      setQuery("")
      setActiveSession(null)
      setActiveProductLabel(null)
      inputRef.current?.focus()
  }
  const handleScrape = async (searchQuery: string, canonicalProduct: CanonicalProduct) => {
      if (isLoading) return
      setIsLoading(true)

      try {
        const data = await scrapeProducts(
          searchQuery,
          canonicalProduct
        );
        const responseData = data?.data
        const products = normalizeProducts(responseData?.products || [])

        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: responseData?.message || "Here are the products I found.",
            products,
            searchQuery,
          },
        ])
      } catch {
        setMessages((prev) => [...prev, { role: "assistant", content: "Scraping failed." }])
      } finally {
        setIsLoading(false)
      }
    }

  return {
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

    sidebarCollapsed,
    setSidebarCollapsed,

    recentCollapsed,
    setRecentCollapsed,

    activeProductLabel,
    setActiveProductLabel,

    messagesScrollRef,
    inputRef,

    handleSend,
    handleNewSearch,
    handleScrape,
  };
}
"use client"
/*
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

// ---------- React core hooks ----------
import { useEffect, useRef, useState } from "react"
// ---------- Icon set used throughout the UI (lucide-react) ----------
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
  Tag,
  X,
} from "lucide-react"

// ============================================================
// THEME TOKENS
// Central color/typography/shadow palette ("T" = Theme).
// Using a single object lets every component reference consistent
// design tokens instead of hardcoding colors everywhere.
// ============================================================
const T = {
  bg0: "#F3EEFB",          // page background base
  bg1: "#FFFFFF",          // plain white surface
  bg2: "#F9F6FF",          // light lavender surface (cards, inputs)
  bg3: "#ECE3FB",          // slightly deeper lavender surface
  border: "#EAE2F8",       // default hairline border color
  borderHi: "rgba(146, 110, 230, 0.28)", // higher-contrast border (unused directly but kept for theme completeness)
  accent: "#8B6CE8",       // primary brand purple
  accentDim: "rgba(139, 108, 232, 0.12)", // translucent accent for backgrounds/badges
  indigo: "#7C5CD6",       // secondary purple, used in gradients with accent
  indigoDim: "rgba(124, 92, 214, 0.12)",
  pink: "#F2A6CB",         // accent pink used in gradients/badges
  pinkDim: "rgba(242, 166, 203, 0.16)",
  coral: "#FB7185",        // extra filter-chip color
  coralDim: "rgba(251, 113, 133, 0.12)",
  sky: "#8FC4F0",          // extra filter-chip color / delivery label color
  skyDim: "rgba(143, 196, 240, 0.16)",
  amber: "#F2B26B",        // star rating / discount-adjacent color
  amberDim: "rgba(242, 178, 107, 0.14)",
  text0: "#2E2640",        // primary (darkest) text color
  text1: "#6B6080",        // secondary text color
  text2: "#A89FBC",        // tertiary/placeholder text color
  glass: "rgba(255, 255, 255, 0.66)",       // translucent glass panel background
  glassSolid: "rgba(255, 255, 255, 0.86)",  // more opaque glass background (cards, bubbles)
  shadow: "0 8px 28px rgba(139, 108, 232, 0.14)",      // stronger drop shadow
  shadowSoft: "0 4px 16px rgba(139, 108, 232, 0.10)",  // subtler drop shadow
  display: '"Quicksand", "Plus Jakarta Sans", sans-serif', // heading/display font stack
  mono: '"Plus Jakarta Sans", sans-serif',                  // "mono-style" labels (not a real monospace, just reused stack)
  sans: '"Plus Jakarta Sans", sans-serif',                  // body font stack
} as const

// ============================================================
// TYPE DEFINITIONS
// ============================================================

// Shape of a single product result returned from the backend scraper.
// Many fields are optional since different stores/responses may omit some.
type Product = {
  store?: string
  productname?: string
  title?: string
  priceinr?: number
  originalprice?: number
  discountpercent?: number
  productlink?: string
  url?: string
  image?: string
  rating?: number
  reviewcount?: number
  deliverylabel?: string
  isbestprice?: boolean
  isreliable?: boolean
}

// The "canonical product" is the structured representation of what Gemini
// parsed out of the user's natural-language query (brand, model, filters, etc).
// Left as a generic record since its keys vary by product category.
type CanonicalProduct = Record<string, unknown>

// A single chat message, either from the user or the assistant.
// Extra optional fields (options, products, filters, etc.) let one message
// type carry very different kinds of assistant responses.
type Message = {
  role: "user" | "assistant"
  content: string
  options?: string[]              // quick-reply buttons (e.g. clarification choices)
  optionUsed?: boolean            // once an option is clicked, hide the buttons
  products?: Product[]            // scraped product results to render as cards
  searchQuery?: string            // the resolved search query tied to this message
  filters?: Record<string, string[]> // filters associated with this message (rarely used directly here)
  canonicalProduct?: CanonicalProduct // parsed product details (shown in the "Extracted details" panel)
  parsedSearchQuery?: string      // search query string derived from the canonical product parse step
}

// One entry in the "recent searches" sidebar — stores the original query,
// the full message history for that session, and any filters that were active.
type SessionEntry = {
  query: string
  messages: Message[]
  filters: Record<string, unknown>
}

// Shape of whatever the FastAPI backend returns from /search or /scrape.
// Includes both snake_case and camelCase variants because the backend's
// naming has been inconsistent across iterations, so the frontend defensively
// checks all of them.
type BackendResponse = {
  data?: {
    type?: string
    message?: string
    options?: string[]
    products?: Product[]
    search_query?: string
    searchquery?: string
    searchQuery?: string
    filters?: Record<string, unknown>
    canonical_product?: CanonicalProduct
    canonicalproduct?: CanonicalProduct
    canonicalProduct?: CanonicalProduct
    parsedsearchquery?: string
    parsedSearchQuery?: string
  }
  message?: string
}

// Suggested search chips shown on the empty/home state.
const QUICKCHIPS = [
  "iPhone 15",
  "Sony WH-1000XM5",
  "Gaming laptop under 60k",
  "boAt headphones",
  "Smartwatch under 5k",
] as const

// Brand colors used to tint the "STORE" label and the "View on <store>" button
// per retailer, so Amazon/Flipkart/Myntra are visually distinguishable.
const STORECOLORS: Record<string, string> = {
  amazon: "#FF9900",
  flipkart: "#2874F0",
  myntra: "#FF3F6C",
}

// Rotating palette used to color-code dynamic filter groups and quick chips,
// so each group/chip gets a different accent color in sequence.
const FILTERCOLORS: string[] = [T.accent, T.pink, T.sky, T.coral, T.amber]

// Picks a color from FILTERCOLORS by index, wrapping around with modulo
// so any number of filter groups/chips still gets a color.
function filterColor(index: number) {
  return FILTERCOLORS[index % FILTERCOLORS.length]
}

/* ---------- Robo mascot, the signature element ---------- */
// Renders the small robot-head logo/icon used in the header, sidebar,
// and next to every assistant chat bubble. `id` is used to make the
// SVG gradient ID unique per instance (otherwise multiple robots on
// the page would all share/clobber the same gradient definition).
function RoboIcon({ size = 16, id = "ri" }: { size?: number; id?: string }) {
  const gradId = `roboGrad-${id}`
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        {/* Gradient used for the robot's ears and head shell */}
        <linearGradient id={gradId} x1="8" y1="4" x2="40" y2="44" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#C9B6F7" />
          <stop offset="55%" stopColor="#8B6CE8" />
          <stop offset="100%" stopColor="#6E4FCC" />
        </linearGradient>
      </defs>
      {/* Ears */}
      <ellipse cx="14" cy="38" rx="4.5" ry="3" fill={`url(#${gradId})`} opacity="0.55" />
      <ellipse cx="34" cy="38" rx="4.5" ry="3" fill={`url(#${gradId})`} opacity="0.55" />
      {/* Antenna */}
      <rect x="20.5" y="2" width="3" height="6" rx="1.5" fill={`url(#${gradId})`} />
      <circle cx="22" cy="3.5" r="2.4" fill="#F2A6CB" />
      {/* Head shell */}
      <rect x="6" y="9" width="36" height="30" rx="15" fill={`url(#${gradId})`} />
      <rect x="6" y="9" width="36" height="30" rx="15" fill="white" fillOpacity="0.06" />
      {/* Eyes */}
      <ellipse cx="16.5" cy="24" rx="3.3" ry="4.4" fill="#2E2640" />
      <ellipse cx="31.5" cy="24" rx="3.3" ry="4.4" fill="#2E2640" />
      {/* Eye highlights/sparkle */}
      <ellipse cx="15.3" cy="22" rx="1.1" ry="1.4" fill="white" opacity="0.85" />
      <ellipse cx="30.3" cy="22" rx="1.1" ry="1.4" fill="white" opacity="0.85" />
    </svg>
  )
}

// Renders chat message text, supporting:
// - newlines (split into separate divs/lines)
// - **bold** markdown-style segments (rendered as <strong>)
// This is a minimal, hand-rolled markdown renderer (not a full parser).
function renderContent(text: string) {
  return text.split("\n").map((line, li) => {
    // Split each line on **bold** markers, keeping the markers in the array
    // (via the capturing group) so we know which segments to bold.
    const parts = line.split(/(\*\*.*?\*\*)/)
    return (
      <div key={li} style={{ minHeight: line ? 6 : undefined }}>
        {parts.map((part, pi) =>
          part.startsWith("**") && part.endsWith("**") ? (
            <strong key={pi} style={{ color: T.text0, fontWeight: 700 }}>
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

// Renders a 5-star rating row, filling stars up to the rounded rating value.
function StarRating({ rating }: { rating: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          size={10}
          fill={i <= Math.round(rating) ? T.amber : "none"}
          color={i <= Math.round(rating) ? T.amber : T.text2}
        />
      ))}
    </div>
  )
}

// ============================================================
// ProductCard
// Renders a single scraped product as a glassmorphism card:
// image, store badge, title, price (with strikethrough original price),
// discount badge, rating, delivery label, and a link out to the store.
// ============================================================
function ProductCard({ product }: { product: Product; key?: string | number }) {
  // Tracks whether the product image failed to load, to fall back to a placeholder icon.
  const [imgError, setImgError] = useState(false)
  // Tracks hover state to drive the lift/translate animation.
  const [hover, setHover] = useState(false)

  const store = product.store || "Unknown"
  const storeColor = STORECOLORS[store.toLowerCase()] || T.indigo
  const title = product.productname || product.title || "Product"
  const price = product.priceinr ? product.priceinr.toLocaleString("en-IN") : "NA"

  // Only show the "original price" strikethrough if it's actually higher than the current price.
  const origPrice =
    product.originalprice && product.originalprice > (product.priceinr || 0)
      ? product.originalprice.toLocaleString("en-IN")
      : null

  // Only show a discount badge if a positive discount percentage exists.
  const discount =
    product.discountpercent && product.discountpercent > 0
      ? `${product.discountpercent}% off`
      : null

  const link = product.productlink || product.url

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        background: T.glassSolid,
        backdropFilter: "blur(14px)",
        // Best-price cards get a subtle accent-tinted border to stand out.
        border: product.isbestprice
          ? `1px solid ${T.accent}55`
          : `1px solid ${T.border}`,
        borderRadius: 24,
        display: "flex",
        flexDirection: "column",
        width: 280,
        minWidth: 280,
        maxWidth: 280,
        flexShrink: 0,
        position: "relative",
        overflow: "hidden",

        // Lift the card slightly on hover for a tactile feel.
        transform: hover ? "translateY(-6px)" : "translateY(0)",
        transition: "all 0.25s ease",

        boxShadow: "0 18px 45px rgba(139,108,232,.18)",
      }}
    >
      {/* Top accent strip shown only on the "best price" card */}
      {product.isbestprice ? (
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 3,
            background: `linear-gradient(90deg, ${T.accent}, ${T.pink})`,
          }}
        />
      ) : null}

      {/* Product image area, with placeholder icon fallback */}
      <div
        style={{
          height: 170,
          background:
            "linear-gradient(180deg,#F9F7FF 0%,#F3EEFB 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {product.image && !imgError ? (
          <img
            src={product.image}
            alt={title}
            referrerPolicy="no-referrer" // avoids some hotlink-blocking issues on store CDNs
            style={{ width: "100%", height: "100%", objectFit: "contain", padding: 18 }}
            onError={() => setImgError(true)}
          />
        ) : (
          <ShoppingBag size={28} color={T.text2} />
        )}
      </div>

      {/* Text/details section of the card */}
      <div style={{ padding: 13, display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
        {/* Store name + best-price badge row */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: storeColor,
              letterSpacing: "0.04em",
              fontFamily: T.mono,
            }}
          >
            {store.toUpperCase()}
          </span>
          {product.isbestprice ? (
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                color: "#fff",
                background: `linear-gradient(90deg, ${T.accent}, ${T.pink})`,
                padding: "2px 7px",
                borderRadius: 6,
                fontFamily: T.mono,
              }}
            >
              BEST PRICE
            </span>
          ) : null}
        </div>

        {/* Product title, clamped to 3 lines to keep card heights consistent */}
        <div
          style={{
            fontSize: 15,
            fontWeight: 700,
            color: T.text0,
            lineHeight: 1.4,
            overflow: "hidden",
            display: "-webkit-box",
            WebkitLineClamp: 3,
            WebkitBoxOrient: "vertical",
          }}
        >
          {title}
        </div>

        {/* Price row: current price + optional strikethrough original price */}
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span style={{ fontSize: 28, fontWeight: 700, color: T.text0, fontFamily: T.mono }}>
            ₹{price}
          </span>
          {origPrice ? (
            <span
              style={{
                fontSize: 11,
                color: T.text2,
                textDecoration: "line-through",
                fontFamily: T.mono,
              }}
            >
              ₹{origPrice}
            </span>
          ) : null}
        </div>

        {/* Discount badge, only rendered when a discount exists */}
        {discount ? (
          <span
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: T.pink,
              background: T.pinkDim,
              padding: "2px 7px",
              borderRadius: 6,
              alignSelf: "flex-start",
              fontFamily: T.mono,
            }}
          >
            {discount}
          </span>
        ) : null}

        {/* Rating + review count, only rendered if a rating is present */}
        {(product.rating || 0) > 0 ? (
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <StarRating rating={product.rating || 0} />
            <span style={{ fontSize: 11, color: T.amber, fontWeight: 600, fontFamily: T.mono }}>
              {(product.rating || 0).toFixed(1)}
            </span>
            {product.reviewcount ? (
              <span style={{ fontSize: 10, color: T.text2 }}>
                {product.reviewcount.toLocaleString("en-IN")}
              </span>
            ) : null}
          </div>
        ) : null}

        {/* Delivery estimate label, if the backend provided one */}
        {product.deliverylabel ? <div style={{ fontSize: 10, color: T.sky }}>{product.deliverylabel}</div> : null}

        {/* "View on <store>" external link button, or a fallback message if no link exists */}
        {link ? (
          <a
            href={link}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 5,
              background: storeColor,
              borderRadius: 14,
              padding: "12px",
              color: "#fff",
              fontSize: 13,
              fontWeight: 700,
              textDecoration: "none",
              marginTop: "auto", // pushes the button to the bottom of the card regardless of content height
              fontFamily: T.sans,
            }}
          >
            View on {store} ↗ <ExternalLink size={10} />
          </a>
        ) : (
          <div
            style={{
              textAlign: "center",
              fontSize: 11,
              color: T.text2,
              padding: 6,
              marginTop: "auto",
            }}
          >
            Link unavailable
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================================
// CanonicalProductDetails
// Collapsible panel shown right after the assistant parses a query,
// displaying the structured fields (brand, model, filters, etc.)
// extracted by Gemini before scraping begins.
// ============================================================
function CanonicalProductDetails({
  data,
  searchQuery,
}: {
  data?: CanonicalProduct
  searchQuery?: string
}) {
  // Expanded by default so the user immediately sees what was parsed.
  const [open, setOpen] = useState(true)

  // Don't render anything if there's no canonical data to show.
  if (!data || Object.keys(data).length === 0) return null

  // Safely stringifies any value type (array, object, primitive) for display.
  const renderValue = (val: unknown): string => {
    if (val === null || val === undefined) return ""
    if (Array.isArray(val)) return val.map(String).join(", ")
    if (typeof val === "object") return JSON.stringify(val)
    return String(val)
  }

  return (
    <div style={{ marginTop: 10, marginLeft: 38, maxWidth: 420 }}>
      {/* Toggle button to expand/collapse the details panel */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          background: "transparent",
          border: "none",
          color: T.accent,
          fontSize: 11,
          fontFamily: T.mono,
          cursor: "pointer",
          padding: "4px 0",
        }}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        Extracted details
      </button>

      {open ? (
        <div
          style={{
            marginTop: 6,
            borderRadius: 16,
            border: `1px solid ${T.border}`,
            background: T.glassSolid,
            backdropFilter: "blur(14px)",
            padding: "10px 12px",
            boxShadow: T.shadowSoft,
          }}
        >
          {/* Show the resolved search query as its own row, if provided */}
          {searchQuery ? (
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "3px 0", fontSize: 11 }}>
              <span style={{ color: T.text2, fontFamily: T.mono }}>searchQuery</span>
              <span style={{ color: T.sky, fontFamily: T.mono, textAlign: "right" }}>{searchQuery}</span>
            </div>
          ) : null}

          {/* Render each top-level field of the canonical product object.
              Nested objects (but not arrays) are flattened into "key.subKey" rows
              so structures like { filters: { color: "black" } } display nicely. */}
          {Object.entries(data).map(([key, val]) =>
            val !== null && typeof val === "object" && !Array.isArray(val) ? (
              Object.entries(val as Record<string, unknown>).map(([subKey, subVal]) => (
                <div key={`${key}.${subKey}`} style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "3px 0", fontSize: 11 }}>
                  <span style={{ color: T.text2, fontFamily: T.mono }}>{key}.{subKey}</span>
                  <span style={{ color: T.indigo, fontFamily: T.mono, textAlign: "right" }}>
                    {renderValue(subVal)}
                  </span>
                </div>
              ))
            ) : (
              <div key={key} style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "3px 0", fontSize: 11 }}>
                <span style={{ color: T.text2, fontFamily: T.mono }}>{key}</span>
                <span style={{ color: T.accent, fontFamily: T.mono, textAlign: "right" }}>
                  {renderValue(val)}
                </span>
              </div>
            ),
          )}
        </div>
      ) : null}
    </div>
  )
}

// ============================================================
// FilterSidebar
// Right-hand collapsible panel showing dynamic, backend-driven filter
// chips (e.g. brand, storage, color) for the current search. Lets the
// user multi-select chips per group, type a custom value, and apply
// the combined filter selection by sending a follow-up query.
// ============================================================
function FilterSidebar({
  collapsed,
  onToggle,
  dynamicFilters,
  onApply,
}: {
  collapsed: boolean
  onToggle: () => void
  dynamicFilters: Record<string, unknown>
  onApply: (query: string) => void
}) {
  // Tracks which chip values are selected per filter group (group -> set of selected values).
  const [selected, setSelected] = useState<Record<string, Set<string>>>({})
  // Tracks the current text typed into each group's "custom value" input.
  const [customInputs, setCustomInputs] = useState<Record<string, string>>({})
  // Tracks whether the custom-value input row is visible per group.
  const [showCustomInput, setShowCustomInput] = useState<Record<string, boolean>>({})

  const hasFilters = Object.keys(dynamicFilters).length > 0

  // Whenever the backend sends a new set of dynamic filters (i.e. a new search),
  // reset all local selection/input state so stale selections don't linger.
  useEffect(() => {
    setSelected({})
    setCustomInputs({})
    setShowCustomInput({})
  }, [dynamicFilters])

  // Toggles a single chip value on/off within its filter group.
  const toggle = (group: string, value: string) => {
    setSelected((prev) => {
      const next = { ...prev }
      const groupSet = new Set(prev[group] || [])
      groupSet.has(value) ? groupSet.delete(value) : groupSet.add(value)
      next[group] = groupSet
      return next
    })
  }

  // Total count of selected chips across all groups, shown as a badge.
  const totalSelected = (Object.values(selected) as Set<string>[]).reduce((sum, s) => sum + s.size, 0)

  // Builds a single human-readable filter query string from current selections
  // (and/or custom typed values) and sends it up via onApply.
  // Groups with nothing selected are explicitly marked "any" so the backend
  // knows the user has no preference for that group.
  const handleApply = () => {
    const parts: string[] = []

    for (const group of Object.keys(dynamicFilters)) {
      // A typed custom value takes priority over chip selections for that group.
      const customVal = customInputs[group]?.trim()
      if (customVal) {
        parts.push(`${group}: ${customVal}`)
        continue
      }

      const vals = selected[group]
      // Strip out the synthetic "No preference" value before combining real selections.
      const realVals = vals ? [...vals].filter((v) => v !== "No preference") : []

      if (realVals.length > 0) {
        parts.push(`${group}: ${realVals.join("/")}`)
      } else {
        parts.push(`${group}: any`)
      }
    }

    onApply(parts.join(", "))
  }

  // Adds the currently typed custom value as a selected chip for that group,
  // then clears the input and hides the custom-input row.
  const handleCustomAdd = (group: string) => {
    const val = customInputs[group]?.trim()
    if (!val) return
    setSelected((prev) => {
      const next = { ...prev }
      const groupSet = new Set(prev[group] || [])
      groupSet.add(val)
      next[group] = groupSet
      return next
    })
    setCustomInputs((prev) => ({ ...prev, [group]: "" }))
    setShowCustomInput((prev) => ({ ...prev, [group]: false }))
  }

  return (
    <aside
      style={{
        // Collapses to a thin strip (just an icon/badge) vs full width when expanded.
        width: collapsed ? 44 : 234,
        flexShrink: 0,
        background: T.glass,
        backdropFilter: "blur(20px)",
        borderLeft: `1px solid ${T.border}`,
        display: "flex",
        flexDirection: "column",
        transition: "width 0.22s cubic-bezier(.4,0,.2,1)",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* Collapse/expand toggle button, pinned to top-left of the sidebar */}
      <button
        type="button"
        onClick={onToggle}
        style={{
          position: "absolute",
          top: 14,
          left: collapsed ? 6 : 10,
          width: 24,
          height: 24,
          borderRadius: 9,
          border: `1px solid ${T.border}`,
          background: T.bg2,
          color: T.text2,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          zIndex: 2,
          flexShrink: 0,
        }}
      >
        {collapsed ? <ChevronLeft size={12} /> : <ChevronRight size={12} />}
      </button>

      {!collapsed ? (
        // ---------- Expanded sidebar content ----------
        <>
          {/* Header */}
          <div style={{ padding: "16px 14px 12px", borderBottom: `1px solid ${T.border}`, flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: T.text2, fontFamily: T.mono, paddingLeft: 32 }}>
              <SlidersHorizontal size={10} />
              Refine search
            </div>
          </div>

          {/* Scrollable list of filter groups */}
          <div style={{ flex: 1, overflowY: "auto", padding: "10px 0" }}>
            {/* Empty state shown before any search has produced filters */}
            {!hasFilters ? (
              <div style={{ padding: "32px 16px", display: "flex", flexDirection: "column", alignItems: "center", gap: 12, textAlign: "center" }}>
                <div style={{ width: 42, height: 42, borderRadius: 14, background: T.bg2, border: `1px dashed ${T.border}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <SlidersHorizontal size={16} color={T.text2} />
                </div>
                <div style={{ fontSize: 12, color: T.text2, lineHeight: 1.6 }}>
                  Filters appear here after you search
                </div>
              </div>
            ) : null}

            {/* One block per filter group (e.g. "brand", "storage", "color") */}
            {Object.entries(dynamicFilters).map(([group, values], gi) => {
              const col = filterColor(gi)
              let rawValues: string[] = []

              // Backend may send either a plain array of options, or an
              // object like { options: [...] } — handle both shapes.
              if (Array.isArray(values)) {
                rawValues = values.map(String)
              } else if (
                values &&
                typeof values === "object" &&
                "options" in values
              ) {
                rawValues = ((values as { options: string[] }).options || []).map(String)
              }

              // Clean up echoed "any"/"none"/etc. placeholder values so they
              // don't show up as selectable chips (a real value or nothing
              // should be shown, not a literal "Any" chip).
              const normalizedValues = rawValues
                .map(String)
                .map((v) => v.trim())
                .filter(
                  (v) =>
                    v &&
                    v.toLowerCase() !== "any" &&
                    v.toLowerCase() !== "none" &&
                    v.toLowerCase() !== "null" &&
                    v.toLowerCase() !== "undefined",
                )

              return (
                <div key={group} style={{ marginBottom: 6 }}>
                  {/* Group header: colored tick mark + group name + "add custom value" button */}
                  <div style={{ display: "flex", alignItems: "center", padding: "6px 14px 5px", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                      <div style={{ width: 3, height: 12, borderRadius: 2, background: col, flexShrink: 0 }} />
                      <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.09em", textTransform: "uppercase", color: col, fontFamily: T.mono }}>
                        {group.replace(/_/g, " ")}
                      </span>
                    </div>
                    <button
                      type="button"
                      title="Type a custom value"
                      onClick={() => setShowCustomInput((prev) => ({ ...prev, [group]: !prev[group] }))}
                      style={{ background: "transparent", border: "none", color: T.text2, cursor: "pointer", padding: "0 2px", display: "flex", alignItems: "center" }}
                    >
                      <Plus size={11} />
                    </button>
                  </div>

                  {/* Chip row for this group's options */}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 5, padding: "0 13px 8px" }}>
                    {normalizedValues.map((val) => {
                      const isOn = selected[group]?.has(val)
                      return (
                        <button
                          key={val}
                          type="button"
                          onClick={() => toggle(group, val)}
                          style={{
                            padding: "4px 11px",
                            borderRadius: 20,
                            fontSize: 11,
                            fontWeight: isOn ? 600 : 400,
                            border: isOn ? `1px solid ${col}66` : `1px solid ${T.border}`,
                            background: isOn ? `${col}15` : "transparent",
                            color: isOn ? col : T.text1,
                            cursor: "pointer",
                            fontFamily: T.mono,
                            transition: "all 0.12s",
                          }}
                        >
                          {val}
                        </button>
                      )
                    })}
                  </div>

                  {/* Custom-value text input, shown only when the "+" button was clicked for this group */}
                  {showCustomInput[group] ? (
                    <div style={{ display: "flex", gap: 5, padding: "0 13px 8px" }}>
                      <input
                        type="text"
                        placeholder={`Type ${group.replace(/_/g, " ").toLowerCase()}`}
                        value={customInputs[group] || ""}
                        onChange={(e) => setCustomInputs((prev) => ({ ...prev, [group]: e.target.value }))}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") handleCustomAdd(group)
                        }}
                        style={{
                          flex: 1,
                          padding: "4px 8px",
                          borderRadius: 8,
                          border: `1px solid ${col}55`,
                          background: T.bg2,
                          color: T.text0,
                          fontSize: 11,
                          fontFamily: T.mono,
                          outline: "none",
                        }}
                      />
                      <button
                        type="button"
                        onClick={() => handleCustomAdd(group)}
                        style={{
                          padding: "4px 8px",
                          borderRadius: 8,
                          border: "none",
                          background: col,
                          color: "#fff",
                          fontSize: 11,
                          cursor: "pointer",
                          fontFamily: T.mono,
                        }}
                      >
                        Add
                      </button>
                    </div>
                  ) : null}

                  {/* Dashed divider between filter groups */}
                  <div style={{ margin: "0 14px", height: 1, background: `repeating-linear-gradient(90deg, ${T.border} 0px, ${T.border} 4px, transparent 4px, transparent 8px)` }} />
                </div>
              )
            })}
          </div>

          {/* Row of currently-selected chips (across all groups), each removable via the "x" */}
          <div style={{ padding: "8px 12px 4px", display: "flex", flexWrap: "wrap", gap: 5, borderTop: `1px solid ${T.border}` }}>
            {(Object.entries(selected) as [string, Set<string>][]).flatMap(([group, vals], gi) =>
              [...vals].map((v) => {
                const col = filterColor(gi)
                return (
                  <span
                    key={`${group}-${v}`}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "2px 8px",
                      borderRadius: 4,
                      background: T.bg2,
                      border: `1px solid ${col}44`,
                      color: col,
                      fontSize: 10,
                      fontFamily: T.mono,
                    }}
                  >
                    {v}
                    {/* Removes this single selected value from its group */}
                    <span
                      onClick={() =>
                        setSelected((prev) => {
                          const next = { ...prev }
                          const groupSet = new Set(prev[group] || [])
                          groupSet.delete(v)
                          next[group] = groupSet
                          return next
                        })
                      }
                      style={{ cursor: "pointer", opacity: 0.6, display: "flex" }}
                    >
                      <X size={9} />
                    </span>
                  </span>
                )
              }),
            )}
          </div>

          {/* "Apply filters" call-to-action button, with a badge showing the selected count */}
          <div style={{ padding: "10px 12px 14px", flexShrink: 0 }}>
            <button
              type="button"
              onClick={handleApply}
              style={{
                width: "100%",
                padding: "11px",
                borderRadius: 14,
                border: "none",
                background: `linear-gradient(135deg, ${T.accent}, ${T.indigo})`,
                color: "#fff",
                fontSize: 12,
                fontWeight: 700,
                cursor: "pointer",
                fontFamily: T.mono,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                transition: "all 0.15s",
                letterSpacing: "0.04em",
                boxShadow: T.shadow,
              }}
            >
              <Search size={12} />
              APPLY FILTERS
              {totalSelected > 0 ? (
                <span style={{ background: "rgba(255,255,255,0.25)", borderRadius: 20, padding: "1px 7px", fontSize: 10 }}>
                  {totalSelected}
                </span>
              ) : null}
            </button>
          </div>
        </>
      ) : (
        // ---------- Collapsed sidebar content: just an icon + selection-count badge ----------
        <div style={{ marginTop: 52, display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "0 8px" }}>
          <SlidersHorizontal size={14} color={totalSelected > 0 ? T.accent : T.text2} />
          {totalSelected > 0 ? (
            <span style={{ width: 18, height: 18, borderRadius: "50%", background: T.accent, color: "#fff", fontSize: 10, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: T.mono }}>
              {totalSelected}
            </span>
          ) : null}
        </div>
      )}
    </aside>
  )
}

// ============================================================
// RecentSearchSidebar
// Left-hand collapsible panel listing the app logo/branding and the
// user's recent search sessions, letting them click back into a
// previous conversation (restoring its messages + filters).
// ============================================================
function RecentSearchSidebar({
  collapsed,
  onToggle,
  sessions,
  activeSession,
  onSelect,
}: {
  collapsed: boolean
  onToggle: () => void
  sessions: SessionEntry[]
  activeSession: string | null
  onSelect: (session: SessionEntry) => void
}) {
  const hasSessions = sessions.length > 0

  return (
    <aside
      style={{
        // Collapses to a thin strip vs full width when expanded.
        width: collapsed ? 44 : 220,
        flexShrink: 0,
        background: T.glass,
        backdropFilter: "blur(20px)",
        borderRight: `1px solid ${T.border}`,
        display: "flex",
        flexDirection: "column",
        transition: "width 0.22s cubic-bezier(.4,0,.2,1)",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* Collapse/expand toggle button, pinned to top-right of this sidebar */}
      <button
        type="button"
        onClick={onToggle}
        style={{
          position: "absolute",
          top: 14,
          right: collapsed ? 6 : 10,
          width: 24,
          height: 24,
          borderRadius: 9,
          border: `1px solid ${T.border}`,
          background: T.bg2,
          color: T.text2,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          zIndex: 2,
          flexShrink: 0,
        }}
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>

      {!collapsed ? (
        // ---------- Expanded sidebar content ----------
        <>
          {/* Logo/branding header + "Recent searches" section label */}
          <div style={{ padding: "16px 14px 12px", borderBottom: `1px solid ${T.border}`, flexShrink: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 14, paddingRight: 32 }}>
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 11,
                  background: `linear-gradient(135deg, ${T.bg3}, ${T.pinkDim})`,
                  border: `1px solid ${T.accent}33`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <RoboIcon size={20} id="logo" />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.text0, letterSpacing: "-0.2px", fontFamily: T.display }}>ShopBot</div>
                <div style={{ fontSize: 10, color: T.text2, fontFamily: T.mono }}>Smart Price Finder</div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: T.text2, fontFamily: T.mono }}>
              <Clock size={10} />
              Recent searches
            </div>
          </div>

          {/* Scrollable list of past search sessions */}
          <div style={{ flex: 1, overflowY: "auto", padding: "8px 0" }}>
            {/* Empty state before any searches have been made */}
            {!hasSessions ? (
              <div style={{ padding: "32px 16px", display: "flex", flexDirection: "column", alignItems: "center", gap: 12, textAlign: "center" }}>
                <div style={{ width: 42, height: 42, borderRadius: 14, background: T.bg2, border: `1px dashed ${T.border}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Clock size={16} color={T.text2} />
                </div>
                <div style={{ fontSize: 12, color: T.text2, lineHeight: 1.6 }}>
                  Your recent searches will show up here
                </div>
              </div>
            ) : null}

            {/* One row per saved session, highlighted if it's the currently active one */}
            {sessions.map((s) => {
              const isActive = activeSession === s.query
              return (
                <button
                  key={s.query}
                  type="button"
                  onClick={() => onSelect(s)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    width: "100%",
                    textAlign: "left",
                    padding: "9px 14px",
                    border: "none",
                    borderLeft: isActive ? `2px solid ${T.accent}` : "2px solid transparent",
                    background: isActive ? T.accentDim : "transparent",
                    color: isActive ? T.accent : T.text1,
                    fontSize: 12,
                    fontFamily: T.mono,
                    cursor: "pointer",
                    overflow: "hidden",
                  }}
                >
                  <Search size={11} style={{ flexShrink: 0, opacity: 0.7 }} />
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.query}</span>
                </button>
              )
            })}
          </div>
        </>
      ) : (
        // ---------- Collapsed sidebar content: just an icon + session-count badge ----------
        <div style={{ marginTop: 52, display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: "0 8px" }}>
          <Clock size={14} color={hasSessions ? T.accent : T.text2} />
          {hasSessions ? (
            <span style={{ width: 18, height: 18, borderRadius: "50%", background: T.accent, color: "#fff", fontSize: 10, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: T.mono }}>
              {sessions.length}
            </span>
          ) : null}
        </div>
      )}
    </aside>
  )
}

// ============================================================
// App
// Top-level component: owns chat state, session history, dynamic
// filters, and all network calls to the FastAPI backend (/search,
// /scrape, /session/clear). Renders the home/empty state, the chat
// transcript, the input bar, and both sidebars.
// ============================================================
export default function App() {
  // Current text in the main search/chat input box.
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
  // The dynamic filter groups/options currently shown in the right sidebar,
  // as provided by the backend for the current search.
  const [sidebarDynamicFilters, setSidebarDynamicFilters] = useState<Record<string, unknown>>({})
  // The resolved product/search label shown in the top header bar.
  const [activeProductLabel, setActiveProductLabel] = useState<string | null>(null)

  // Ref to an invisible div at the bottom of the message list, used to auto-scroll into view.
  const messagesEndRef = useRef<HTMLDivElement>(null)
  // Ref to the main text input, used to refocus it after starting a new search.
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to the latest message whenever messages change or loading state toggles
  // (e.g. so the typing indicator is visible as soon as it appears).
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isLoading])

  // Persist the current message list + filters back into the matching session entry
  // in `sessions`, so switching away and back restores the full conversation state
  // instead of re-triggering API calls.
  useEffect(() => {
    if (!activeSession || messages.length === 0) return
    setSessions((prev) =>
      prev.map((s) => (s.query === activeSession ? { ...s, messages, filters: sidebarDynamicFilters } : s)),
    )
  }, [messages, sidebarDynamicFilters, activeSession])

  // Normalizes raw product objects coming from the backend (which may use either
  // snake_case or camelCase field names) into the consistent `Product` shape
  // that the UI components expect.
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

  // Sends the main chat/search query to the backend's /search endpoint and
  // appends the user's message plus the assistant's reply (clarification,
  // parsed-query summary, product results, or filter update) to the transcript.
  //
  // `overrideQuery` lets callers (like quick-chip buttons or clarification
  // option buttons) trigger a send with specific text instead of the input box's value.
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

      if (type === "clarify") {
        // Backend needs more info from the user — show its message and quick-reply options.
        const message = responseData?.message || "Please clarify your request."
        const options = responseData?.options || []
        setMessages((prev) => [...prev, { role: "assistant", content: message, options }])
      } else if (type === "parsed_query") {
        // Backend has parsed the query into a canonical product + filters,
        // but hasn't scraped yet — show the "Extracted details" panel and
        // a "Search Products" button to trigger scraping.
        const canonicalProduct = responseData?.canonical_product
        const searchQuery = responseData?.search_query || text
        const filters = responseData?.filters || {}
        setSidebarDynamicFilters(filters)

        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Got it! Here's what I extracted — scraping is starting now...",
            canonicalProduct,
            parsedSearchQuery: searchQuery,
          },
        ])
        if (searchQuery) setActiveProductLabel(searchQuery)
      } else if (type === "products") {
        // Backend has finished scraping — normalize and render the product cards,
        // plus a short recommendation sentence about the best deal found.
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
          // Only consider "reliable" products with a valid price when building the recommendation text.
          const reliable = products.filter((p) => p.isreliable && p.priceinr && p.priceinr > 0)
          let recommendation = ""
          if (reliable.length >= 2) {
            const best = reliable.find((p) => p.isbestprice)
            const other = reliable.find((p) => !p.isbestprice)
            if (best) {
              recommendation = `Best deal on ${best.store} at ₹${best.priceinr?.toLocaleString("en-IN")}.`
              if (other) {
                recommendation += ` That's ₹${((other.priceinr || 0) - (best.priceinr || 0)).toLocaleString("en-IN")} cheaper than ${other.store}.`
              }
            }
          }

          const content = recommendation
            ? `Here are the best prices for ${searchQuery}. ${recommendation}`
            : `Here are the best prices I found for ${searchQuery}.`

          setMessages((prev) => [...prev, { role: "assistant", content, products, searchQuery }])
        }
      } else if (type === "filters") {
        // Backend sent an updated filter set without new products (e.g. after refining intent).
        const message = responseData?.message || ""
        const filters = responseData?.filters || {}
        setSidebarDynamicFilters(filters)
        setMessages((prev) => [...prev, { role: "assistant", content: message }])
      } else {
        // Fallback: unknown/unspecified response type — just show whatever message text exists.
        const message = responseData?.message || data?.message || "No response received."
        setMessages((prev) => [...prev, { role: "assistant", content: message }])
      }
    } catch {
      // Network/parsing failure — surface a friendly error instead of crashing.
      setMessages((prev) => [...prev, { role: "assistant", content: "Unable to connect to backend. Please check if the server is running." }])
    } finally {
      setIsLoading(false)
    }
  }

  // Explicitly triggers scraping for an already-parsed canonical product
  // (used by the "Search Products" button shown under the parsed-query message),
  // hitting the /scrape endpoint directly rather than going back through /search.
  const handleScrape = async (searchQuery: string, canonicalProduct: CanonicalProduct) => {
    if (isLoading) return
    setIsLoading(true)

    try {
      const response = await fetch("http://127.0.0.1:8000/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ search_query: searchQuery, canonical_product: canonicalProduct }),
      })

      const data: BackendResponse = await response.json()
      const responseData = data?.data
      const products = normalizeProducts(responseData?.products || [])

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Here are the best prices for ${searchQuery}.`,
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

  // Sends a filter-refinement query (built by FilterSidebar's "Apply filters" button)
  // back through the same /search endpoint, appending the combined filter string
  // to the original query context. Mirrors handleSend's response-handling logic
  // but with a distinct "Filter: ..." display label for the user's message bubble.
  const handleSendFilters = async (filterQuery: string) => {
    if (isLoading) return
    // Fall back to the active session's original query (or whatever's in the input box)
    // if no explicit filter text was given (i.e. "Apply" was clicked with nothing selected).
    const effectiveQuery = filterQuery.trim() || activeSession || query.trim()
    if (!effectiveQuery) return

    const displayText = filterQuery.trim() ? `Filter: ${filterQuery}` : "Any / no filter"
    setMessages((prev) => [...prev, { role: "user", content: displayText }])
    setIsLoading(true)

    try {
      const response = await fetch("http://127.0.0.1:8000/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: effectiveQuery, session_id: sessionId }),
      })

      const data: BackendResponse = await response.json()
      const responseData = data?.data
      const type = responseData?.type || data?.message

      // NOTE: this branch mirrors handleSend's response handling above,
      // just keyed off `effectiveQuery` instead of `text`.
      if (type === "clarify") {
        const message = responseData?.message || "Please clarify your request."
        const options = responseData?.options || []
        setMessages((prev) => [...prev, { role: "assistant", content: message, options }])
      } else if (type === "parsed_query") {
        const canonicalProduct = responseData?.canonical_product
        const searchQuery = responseData?.search_query || effectiveQuery
        const filters = responseData?.filters || {}
        setSidebarDynamicFilters(filters)

        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: "Got it! Here's what I extracted — scraping is starting now...",
            canonicalProduct,
            parsedSearchQuery: searchQuery,
          },
        ])
        if (searchQuery) setActiveProductLabel(searchQuery)
      } else if (type === "products") {
        const products = normalizeProducts(responseData?.products || [])
        const searchQuery = responseData?.search_query || effectiveQuery
        if (searchQuery) setActiveProductLabel(searchQuery)

        if (products.length === 0) {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: `No products found for ${searchQuery}.`,
            },
          ])
        } else {
          const reliable = products.filter((p) => p.isreliable && p.priceinr && p.priceinr > 0)
          let recommendation = ""
          if (reliable.length >= 2) {
            const best = reliable.find((p) => p.isbestprice)
            const other = reliable.find((p) => !p.isbestprice)
            if (best) {
              recommendation = `Best deal on ${best.store} at ₹${best.priceinr?.toLocaleString("en-IN")}.`
              if (other) {
                recommendation += ` That's ₹${((other.priceinr || 0) - (best.priceinr || 0)).toLocaleString("en-IN")} cheaper than ${other.store}.`
              }
            }
          }

          const content = recommendation
            ? `Here are the best prices for ${searchQuery}. ${recommendation}`
            : `Here are the best prices I found for ${searchQuery}.`

          setMessages((prev) => [...prev, { role: "assistant", content, products, searchQuery }])
        }
      } else if (type === "filters") {
        const message = responseData?.message || ""
        const filters = responseData?.filters || {}
        setSidebarDynamicFilters(filters)
        setMessages((prev) => [...prev, { role: "assistant", content: message }])
      } else {
        const message = responseData?.message || data?.message || "No response received."
        setMessages((prev) => [...prev, { role: "assistant", content: message }])
      }
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Unable to connect to backend. Please check if the server is running." }])
    } finally {
      setIsLoading(false)
    }
  }

  // Resets the entire conversation: tells the backend to clear its session state,
  // generates a fresh session ID, and clears all local UI state back to the home screen.
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
    setSidebarDynamicFilters({})
    inputRef.current?.focus()
  }

  // Whether to show the big empty/home hero state vs. the chat transcript.
  const isHome = messages.length === 0

  return (
    <div
      style={{
        display: "flex",
        height: "100vh",
        color: T.text0,
        fontFamily: T.sans,
        overflow: "hidden",
        position: "relative",
        background: T.bg0,
        // Decorative soft-glow radial gradients in each corner, giving the
        // glassmorphism background its colorful ambient look.
        backgroundImage: `
          radial-gradient(38% 32% at 8% 6%, rgba(242,166,203,0.40) 0%, rgba(242,166,203,0) 100%),
          radial-gradient(40% 36% at 96% 10%, rgba(143,196,240,0.38) 0%, rgba(143,196,240,0) 100%),
          radial-gradient(46% 42% at 30% 96%, rgba(139,108,232,0.30) 0%, rgba(139,108,232,0) 100%),
          radial-gradient(38% 38% at 88% 92%, rgba(201,182,247,0.40) 0%, rgba(201,182,247,0) 100%)
        `,
      }}
    >
      {/* Left sidebar: branding + recent search sessions */}
      <RecentSearchSidebar
        collapsed={recentCollapsed}
        onToggle={() => setRecentCollapsed((v) => !v)}
        sessions={sessions}
        activeSession={activeSession}
        onSelect={(s) => {
          // Restore the full state of a previously saved session.
          setMessages(s.messages)
          setActiveSession(s.query)
          setActiveProductLabel(s.query)
          setSidebarDynamicFilters(s.filters)
        }}
      />

      {/* Center column: header bar, chat transcript / home state, and input bar */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0, position: "relative", zIndex: 1 }}>
        {/* Top header bar: live indicator dot, current label, store-coverage badge, "New" button */}
        <div style={{ padding: "11px 22px", borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0, background: "rgba(243,238,251,0.7)", backdropFilter: "blur(14px)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 7, height: 7, borderRadius: "50%", background: T.accent, boxShadow: `0 0 6px ${T.accent}` }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: T.text0, fontFamily: T.display }}>
              {activeProductLabel || activeSession || "ShopBot"}
            </span>
            {/* <span style={{ fontSize: 10, color: T.text2, background: T.bg2, border: `1px solid ${T.border}`, padding: "2px 8px", borderRadius: 20, fontFamily: T.mono }}>
              amz / fk
            </span> */}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button
              type="button"
              onClick={handleNewSearch}
              style={{ display: "flex", alignItems: "center", gap: 5, padding: "6px 13px", borderRadius: 20, border: `1px solid ${T.border}`, background: T.bg1, color: T.text1, fontSize: 11, cursor: "pointer", fontFamily: T.mono, transition: "all 0.13s" }}
            >
              <Plus size={12} />
              New
            </button>
          </div>
        </div>

        {isHome ? (
          // ---------- Home/empty state: hero heading, mascot, quick chips ----------
          <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 32px", gap: 26 }}>
            <div style={{ textAlign: "center" }}>
              <div
                style={{
                  width: 84,
                  height: 84,
                  borderRadius: 26,
                  background: `linear-gradient(150deg, ${T.bg3}, ${T.pinkDim})`,
                  border: `1px solid ${T.accent}33`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 20px",
                  boxShadow: T.shadow,
                }}
              >
                <RoboIcon size={48} id="hero" />
              </div>
              <div style={{ fontSize: 27, fontWeight: 700, color: T.text0, marginBottom: 8, letterSpacing: "-0.5px", fontFamily: T.display }}>
                What are you <span style={{ color: T.accent }}>shopping</span> for?
              </div>
              {/* <div style={{ fontSize: 13, color: T.text1, fontFamily: T.sans }}>
                I&apos;ll compare prices across Amazon & Flipkart instantly
              </div> */}
            </div>

            {/* Quick-search suggestion chips; clicking one immediately sends that query */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center", maxWidth: 500 }}>
              {QUICKCHIPS.map((chip, i) => {
                const col = filterColor(i)
                return (
                  <button
                    key={chip}
                    type="button"
                    onClick={() => handleSend(chip)}
                    style={{
                      padding: "8px 16px",
                      borderRadius: 20,
                      border: `1px solid ${col}33`,
                      background: T.glassSolid,
                      backdropFilter: "blur(10px)",
                      color: T.text1,
                      fontSize: 12,
                      cursor: "pointer",
                      fontFamily: T.mono,
                      transition: "all 0.13s",
                    }}
                    // Inline hover handlers (rather than CSS :hover) since styles are all inline here.
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = `${col}88`
                      e.currentTarget.style.color = col
                      e.currentTarget.style.background = `${col}15`
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = `${col}33`
                      e.currentTarget.style.color = T.text1
                      e.currentTarget.style.background = T.glassSolid
                    }}
                  >
                    <Tag size={9} style={{ marginRight: 5, verticalAlign: "middle" }} />
                    {chip}
                  </button>
                )
              })}
            </div>

            {/* <div style={{ fontSize: 11, color: T.text2, fontFamily: T.mono, display: "flex", alignItems: "center", gap: 6 }}>
              <SlidersHorizontal size={11} color={T.text2} />
              Filters appear on the right after your search
            </div> */}
          </div>
        ) : (
          // ---------- Chat transcript view ----------
          <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px 16px", display: "flex", flexDirection: "column", gap: 18 }}>
            {messages.map((msg, i) => (
              <div key={i} style={{ display: "flex", flexDirection: "column" }}>
                {/* Message bubble row: user bubbles align right (no avatar), assistant bubbles align left with the robot avatar */}
                <div style={{ display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start", alignItems: "flex-start", gap: 10 }}>
                  {msg.role === "assistant" ? (
                    <div
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: "50%",
                        background: `linear-gradient(150deg, ${T.bg3}, ${T.pinkDim})`,
                        border: `1px solid ${T.accent}44`,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                        marginTop: 2,
                      }}
                    >
                      <RoboIcon size={17} id={`msg-${i}`} />
                    </div>
                  ) : null}
                  <div
                    style={{
                      maxWidth: "72%",
                      // Speech-bubble "tail" corner differs depending on sender.
                      borderRadius: msg.role === "user" ? "18px 18px 5px 18px" : "5px 18px 18px 18px",
                      background: msg.role === "user" ? `linear-gradient(135deg, ${T.accent}, ${T.indigo})` : T.glassSolid,
                      backdropFilter: msg.role === "user" ? undefined : "blur(14px)",
                      border: msg.role === "user" ? "none" : `1px solid ${T.border}`,
                      boxShadow: msg.role === "user" ? T.shadowSoft : T.shadowSoft,
                      padding: "11px 15px",
                      fontSize: 13,
                      lineHeight: 1.65,
                      color: msg.role === "user" ? "#fff" : T.text1,
                      fontFamily: T.sans,
                    }}
                  >
                    {renderContent(msg.content)}
                  </div>
                </div>

                {/* Horizontally-scrolling row of product cards, if this assistant message carries results */}
                {msg.role === "assistant" && msg.products && msg.products.length > 0 ? (
                  <div style={{ marginTop: 12, marginLeft: 38 }}>
                    <div style={{ display: "flex", gap: 12, overflowX: "auto", paddingBottom: 4 }}>
                      {msg.products.map((product, pi) => (
                        <ProductCard key={pi} product={product} />
                      ))}
                    </div>
                  </div>
                ) : null}

                {/* Canonical-product details panel + "Search Products" trigger button,
                    shown only on the "parsed_query" type message */}
                {msg.role === "assistant" && msg.canonicalProduct ? (
                  <>
                    <CanonicalProductDetails data={msg.canonicalProduct} searchQuery={msg.parsedSearchQuery} />

                    <button
                      onClick={() => handleScrape(msg.parsedSearchQuery || "", msg.canonicalProduct as CanonicalProduct)}
                      style={{
                        marginTop: 10,
                        marginLeft: 38,
                        padding: "11px 22px",
                        borderRadius: 14,
                        border: "none",
                        background: `linear-gradient(135deg, ${T.accent}, ${T.indigo})`,
                        color: "#fff",
                        cursor: "pointer",
                        fontWeight: 700,
                        fontSize: 13,
                        fontFamily: T.sans,
                        boxShadow: T.shadow,
                      }}
                    >
                      Search Products
                    </button>
                  </>
                ) : null}

                {/* Clarification quick-reply option buttons, hidden once one has been clicked (optionUsed) */}
                {msg.role === "assistant" && msg.options && msg.options.length > 0 && !msg.optionUsed ? (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 7, marginTop: 8, marginLeft: 38 }}>
                    {msg.options.map((opt, oi) => {
                      const col = filterColor(oi)
                      return (
                        <button
                          key={opt}
                          type="button"
                          disabled={isLoading}
                          onClick={() => handleSend(opt)}
                          style={{
                            background: T.glassSolid,
                            backdropFilter: "blur(10px)",
                            border: `1px solid ${col}44`,
                            borderRadius: 20,
                            padding: "7px 14px",
                            color: col,
                            fontSize: 12,
                            fontWeight: 500,
                            cursor: isLoading ? "not-allowed" : "pointer",
                            fontFamily: T.mono,
                            opacity: isLoading ? 0.5 : 1,
                            transition: "all 0.13s",
                          }}
                        >
                          {opt}
                        </button>
                      )
                    })}
                  </div>
                ) : null}
              </div>
            ))}

            {/* Typing/loading indicator bubble shown while waiting on the backend */}
            {isLoading ? (
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    background: `linear-gradient(150deg, ${T.bg3}, ${T.pinkDim})`,
                    border: `1px solid ${T.accent}44`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  <RoboIcon size={17} id="loading" />
                </div>
                <div style={{ padding: "11px 17px", borderRadius: "5px 18px 18px 18px", background: T.glassSolid, backdropFilter: "blur(14px)", border: `1px solid ${T.border}`, display: "flex", gap: 4, alignItems: "center", boxShadow: T.shadowSoft }}>
                  {/* Three bouncing dots, each delayed slightly to create a wave effect (see @keyframes bounce below) */}
                  {[0, 1, 2].map((j) => (
                    <span
                      key={j}
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: T.accent,
                        display: "inline-block",
                        animation: `bounce 1.2s ease-in-out ${j * 0.2}s infinite`,
                        opacity: 0.6,
                      }}
                    />
                  ))}
                </div>
              </div>
            ) : null}
            {/* Anchor element used to auto-scroll the transcript to the bottom */}
            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Bottom input bar: text field + send button */}
        <div style={{ padding: "12px 24px 16px", borderTop: `1px solid ${T.border}`, flexShrink: 0, background: "rgba(243,238,251,0.7)", backdropFilter: "blur(14px)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, background: T.glassSolid, backdropFilter: "blur(14px)", border: `1px solid ${T.border}`, borderRadius: 18, padding: "6px 6px 6px 18px", boxShadow: T.shadowSoft, transition: "border-color 0.15s" }}>
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleSend()}
              placeholder="Search any product"
              disabled={isLoading}
              style={{ flex: 1, background: "transparent", border: "none", outline: "none", color: T.text0, fontSize: 13, fontFamily: T.sans }}
            />
            <button
              type="button"
              onClick={() => void handleSend()}
              disabled={!query.trim() || isLoading}
              style={{
                width: 38,
                height: 38,
                borderRadius: 13,
                background: query.trim() && !isLoading ? `linear-gradient(135deg, ${T.accent}, ${T.indigo})` : T.bg3,
                border: "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                cursor: query.trim() && !isLoading ? "pointer" : "default",
                flexShrink: 0,
                transition: "all 0.13s",
                boxShadow: query.trim() && !isLoading ? T.shadow : "none",
              }}
            >
              <Send size={14} color={query.trim() && !isLoading ? "#fff" : T.text2} />
            </button>
          </div>
        </div>
      </main>

      {/* Right sidebar: dynamic filter chips for the active search */}
      <FilterSidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((v) => !v)}
        dynamicFilters={sidebarDynamicFilters}
        onApply={handleSendFilters}
      />

      {/* Global styles: font import, bounce keyframes for the loading dots, thin custom scrollbar, placeholder color */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        @keyframes bounce {
          0%, 80%, 100% { transform: scale(0.7); opacity: 0.4; }
          40% { transform: scale(1); opacity: 1; }
        }
        ::-webkit-scrollbar { width: 3px; height: 3px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(139, 108, 232, 0.18); border-radius: 3px; }
        input::placeholder { color: ${T.text2}; }
      `}</style>
    </div>
  )
}
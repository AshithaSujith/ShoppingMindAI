import { Check, Search } from "lucide-react";

import { T } from "@/styles/theme";
import type { CanonicalProduct } from "@/types";

export default function CanonicalProductDetails({
  data,
  searchQuery,
  onSearch,
  isSearching,
}: {
  data?: CanonicalProduct
  searchQuery?: string
  onSearch?: () => void
  isSearching?: boolean
}) {
  // Don't render anything if there's no canonical data to show.
  if (!data || Object.keys(data).length === 0) return null

  // Turns a raw field key like "energy_rating" or "compressorType" into
  // a friendly label like "Energy rating" / "Compressor type".
  const humanizeKey = (key: string): string => {
    const spaced = key
      .replace(/[_-]+/g, " ")
      .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    const lower = spaced.toLowerCase().trim()
    return lower.charAt(0).toUpperCase() + lower.slice(1)
  }

  // Turns raw values like "main_product" into "Main product" too,
  // since underscores can show up in values as well as keys.
  const humanizeValue = (val: string): string => {
    if (!val.includes("_")) return val
    const spaced = val.replace(/_/g, " ").toLowerCase().trim()
    return spaced.charAt(0).toUpperCase() + spaced.slice(1)
  }

  // Some upstream responses send object fields (like `attributes`) as a
  // Python-dict-style string, e.g. "{'Capacity': '1 ton', 'Rating': '4★'}"
  // instead of real JSON. This detects that shape and converts it into
  // an actual object so it can be flattened into rows like everything else.
  const tryParseDictString = (val: unknown): unknown => {
    if (typeof val !== "string") return val
    const trimmed = val.trim()
    if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return val
    try {
      const asJson = trimmed
        .replace(/'/g, '"')
        .replace(/None/g, "null")
        .replace(/True/g, "true")
        .replace(/False/g, "false")
      return JSON.parse(asJson)
    } catch {
      return val
    }
  }

  // Safely renders any value type (array, object, primitive) as plain text,
  // humanizing snake_case string values along the way.
  const renderValue = (val: unknown): string => {
    if (val === null || val === undefined) return ""
    if (Array.isArray(val)) return val.map((v) => humanizeValue(String(v))).join(", ")
    if (typeof val === "object") {
      return Object.values(val as Record<string, unknown>).map((v) => humanizeValue(String(v))).join(", ")
    }
    return humanizeValue(String(val))
  }

  // Flatten data into a simple list of { label, value } rows.
  type Row = { label: string; value: string }
  const rows: Row[] = []

  Object.entries(data).forEach(([key, rawVal]) => {
    const val = tryParseDictString(rawVal)
    if (val !== null && typeof val === "object" && !Array.isArray(val)) {
      Object.entries(val as Record<string, unknown>).forEach(([subKey, subVal]) => {
        if (subVal === null || subVal === undefined || subVal === "") return
        rows.push({ label: humanizeKey(subKey), value: renderValue(subVal) })
      })
    } else {
      if (val === null || val === undefined || val === "") return
      rows.push({ label: humanizeKey(key), value: renderValue(val) })
    }
  })

  // Rating rows get a gold star prefix instead of plain text.
  const isRatingRow = (label: string) => label.toLowerCase() === "rating"

  return (
    <div style={{ marginTop: 10, marginLeft: 38, marginRight: 20, maxWidth: 720, fontFamily: T.sans }}>
      <div
        className="cpd-card"
        style={{
          borderRadius: 20,
          border: `1px solid ${T.border}`,
          background: T.bg1,
          padding: "18px 24px",
          boxShadow: T.shadowSoft,
        }}
      >
        {/* Headline: the resolved search query, shown as a product title */}
        {searchQuery ? (
          <div
            className="cpd-headline"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 16,
              paddingBottom: 16,
              borderBottom: `1px solid ${T.border}`,
            }}
          >
            <div
              className="cpd-check"
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: T.accentDim,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Check size={14} color={T.accent} />
            </div>
            <span style={{ fontSize: 16, fontWeight: 500, color: T.text0, fontFamily: T.sans, lineHeight: 1.4 }}>
              {searchQuery}
            </span>
          </div>
        ) : null}

        {/* Spec rows: teal-tinted labels above normal-weight values, staggering in on mount */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", rowGap: 16, columnGap: 24 }}>
          {rows.map((row, ri) => (
            <div
              key={row.label}
              className="cpd-row"
              style={{
                borderRadius: 10,
                padding: "4px 8px",
                margin: "-4px -8px",
                animationDelay: `${80 + ri * 55}ms`,
              }}
            >
              <div
                style={{
                  fontSize: 13,
                  color: T.accent,
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                  marginBottom: 5,
                  fontFamily: T.sans,
                  fontWeight: 600,
                }}
              >
                {row.label}
              </div>
              <div style={{ fontSize: 14, color: T.text0, fontWeight: 500, fontFamily: T.sans, display: "flex", alignItems: "center", gap: 4 }}>
                {isRatingRow(row.label) ? (
                  <>
                    {row.value.replace(/[★☆]/g, "").trim()}
                    <span style={{ color: T.amber }}>★</span>
                  </>
                ) : (
                  row.value
                )}
              </div>
            </div>
          ))}
        </div>

        {false && onSearch && (
          <button
            onClick={onSearch}
            disabled={isSearching}
            style={{
              marginTop: 20,
              width: "100%",
              padding: "14px",
              borderRadius: 14,
              border: "none",
              background: isSearching ? "rgba(255,255,255,0.08)" : `linear-gradient(135deg, ${T.accent}, ${T.indigo})`,
              color: "#fff",
              fontSize: 14,
              fontWeight: 700,
              fontFamily: T.sans,
              cursor: isSearching ? "default" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              transition: "opacity 0.2s",
              opacity: isSearching ? 0.7 : 1,
            }}
          >
            <Search size={16} />
            {isSearching ? "Searching..." : "Search Products"}
          </button>
        )}
      </div>

      {/* Scoped animation styles. Class-based (not inline style objects) since
          keyframes can't be expressed as React style props. Reused safely across
          multiple CanonicalProductDetails instances on the same page. */}
      <style>{`
        @keyframes cpdCardIn {
          from { opacity: 0; transform: translateY(10px) scale(0.98); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes cpdCheckPop {
          0%   { opacity: 0; transform: scale(0.4); }
          60%  { opacity: 1; transform: scale(1.15); }
          100% { opacity: 1; transform: scale(1); }
        }
        @keyframes cpdRowIn {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }

        .cpd-card {
          animation: cpdCardIn 0.42s cubic-bezier(0.22, 1, 0.36, 1) both;
        }
        .cpd-headline {
          opacity: 0;
          animation: cpdRowIn 0.4s ease-out 0.05s both;
        }
        .cpd-check {
          animation: cpdCheckPop 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) 0.15s both;
        }
        .cpd-row {
          opacity: 0;
          animation: cpdRowIn 0.38s ease-out both;
          transition: background 0.18s ease, transform 0.18s ease;
        }
        .cpd-row:hover {
          background: ${T.accentDim};
          transform: translateY(-1px);
        }
      `}</style>
    </div>
  )
}
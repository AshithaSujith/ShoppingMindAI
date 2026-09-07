"use client"

import React from "react";
import { T } from "@/styles/theme";
import { motion } from "framer-motion";
import { 
  Check, 
  ChevronRight, 
  Sparkles, 
  TrendingUp, 
  ShieldCheck, 
  Zap,
  ArrowRight,
  Search
} from "lucide-react";

interface CardOption {
  label: string;
  value?: string;
  icon?: string;
}

interface FilterGroup {
  name: string;
  options: string[];
}

interface Card {
  type: string;
  title?: string;
  description?: string;
  options?: (string | CardOption)[];
  groups?: FilterGroup[];
  multi_select?: boolean;
  submit_button?: string;

  show_search?: boolean;
  search_placeholder?: string;
}

/**
 * text: human-readable summary sent as the effective "query" to the backend.
 * filters: optional structured selections (group name -> chosen values),
 * forwarded alongside `text` so the backend can use either representation.
 */
type FilterSubmitHandler = (text: string, filters?: Record<string, string[]>) => void;

interface ChatCardsProps {
  cards: Card[];
  onFilterSubmit: FilterSubmitHandler;
}

export default function ChatCards({ cards, onFilterSubmit }: ChatCardsProps) {
  if (!cards || cards.length === 0) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 12, width: "100%" }}>
      {cards.map((card, idx) => (
        <div key={idx} style={{ width: "100%" }}>
          {card.type === "filters" ? (
            <FilterCard card={card} onFilterSubmit={onFilterSubmit} />
          ) : card.type === "recommendation" ? (
            <RecommendationCard card={card} />
          ) : (
            <OptionCard card={card} onFilterSubmit={onFilterSubmit} />
          )}
        </div>
      ))}
    </div>
  );
}

function OptionCard({ card, onFilterSubmit }: { card: Card, onFilterSubmit: FilterSubmitHandler }) {
  const [searchText, setSearchText] = React.useState("");
  // Older backend card payloads omit show_search. Keep the direct search
  // affordance visible for every option/category card unless explicitly off.
  const showSearch = card.show_search !== false;

  const submitSearch = () => {
    const trimmed = searchText.trim();
    if (!trimmed) return;
    onFilterSubmit(trimmed);
    setSearchText("");
  };

  return (
    <div style={{ 
      background: "rgba(20,20,20,.95)", 
      border: `1px solid ${T.border}`, 
      borderRadius: 24, 
      padding: 28,
      width: "100%",
      maxWidth: "100%",
      minWidth: 0,
      boxSizing: "border-box",
    }}>
      {card.title && (
        <div style={{ fontSize: 13, fontWeight: 700, color: T.text2, marginBottom: 12, textTransform: "uppercase", letterSpacing: "1px" }}>
          {card.title}
        </div>
      )}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {card.options?.map((opt, i) => {
          const label = typeof opt === "string" ? opt : opt.label;
          return (
            <motion.button
              key={i}
              whileHover={{ scale: 1.02, background: "rgba(255, 255, 255, 0.08)" }}
              whileTap={{ scale: 0.98 }}
              onClick={() => onFilterSubmit(label, { [card.title || "Category"]: [label] })}
              style={{
                padding: "10px 18px",
                borderRadius: 14,
                background: "rgba(255, 255, 255, 0.05)",
                border: `1px solid ${T.border}`,
                color: "#fff",
                fontSize: 14,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8
              }}
            >
              {label}
              <ChevronRight size={14} opacity={0.5} />
            </motion.button>
          );
        })}

        {/* Inline search box — typing here bypasses the chips entirely and
            submits raw free text through the same dedicated handler. */}
        {showSearch && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 10px 6px 14px",
              borderRadius: 14,
              background: "rgba(255, 255, 255, 0.03)",
              border: `1px solid ${T.border}`,
              minWidth: 180,
            }}
          >
            <Search size={13} opacity={0.5} color="#fff" />
            <input
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submitSearch()}
              placeholder={card.search_placeholder || "Search here..."}
              style={{
                background: "transparent",
                border: "none",
                outline: "none",
                color: "#fff",
                fontSize: 14,
                fontWeight: 600,
                width: "100%",
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function FilterCard({ card, onFilterSubmit }: { card: Card, onFilterSubmit: FilterSubmitHandler }) {
  const [selected, setSelected] = React.useState<Record<string, string[]>>({});
  const [searchText, setSearchText] = React.useState("");
  // Keep one consolidated free-text path available even for legacy payloads.
  const showSearch = card.show_search !== false;

  const toggleOption = (groupName: string, option: string) => {
    setSelected(prev => {
      const current = prev[groupName] || [];
      const next = current.includes(option) 
        ? current.filter(o => o !== option)
        : [...current, option];
      return { ...prev, [groupName]: next };
    });
  };

  const handleSubmit = () => {
    const activeGroups = Object.entries(selected).filter(([, vals]) => vals.length > 0);
    const parts = activeGroups.map(([group, vals]) => `${group}: ${vals.join(", ")}`);

    const message: string[] = [];

    if (searchText.trim()) {
      message.push(`Product: ${searchText.trim()}`);
    }

    if (parts.length > 0) {
      message.push(`Preferences: ${parts.join(" | ")}`);
    }

    if (message.length === 0) return;

    // Structured filters passed alongside the text summary, keyed by group name.
    const filters = Object.fromEntries(activeGroups) as Record<string, string[]>;

    onFilterSubmit(message.join(" | "), filters);
  };

  return (
    <div style={{ 
      background: "rgba(20, 20, 20, 0.95)", 
      border: `1px solid ${T.accent}40`, 
      borderRadius: 24, 
      padding: 24,
      boxShadow: "0 20px 40px rgba(0,0,0,0.4)",
      width: "100%",
      maxWidth: "900px",
      minWidth: 0,
      boxSizing: "border-box",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <div style={{ width: 32, height: 32, borderRadius: 10, background: `${T.accent}20`, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Sparkles size={16} color={T.accent} />
        </div>
        <div style={{ fontSize: 18, fontWeight: 800, color: "#fff" }}>{card.title || "Refine your search"}</div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {card.groups?.map((group, i) => (
          <div key={i}>
            <div style={{ fontSize: 12, fontWeight: 700, color: T.text2, marginBottom: 10, textTransform: "uppercase" }}>{group.name}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {group.options.map((opt, oi) => {
                const isSelected = selected[group.name]?.includes(opt);
                return (
                  <motion.button
                    key={oi}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => toggleOption(group.name, opt)}
                    style={{
                      padding: "8px 14px",
                      borderRadius: 12,
                      background: isSelected ? `${T.accent}20` : "rgba(255, 255, 255, 0.05)",
                      border: `1px solid ${isSelected ? T.accent : T.border}`,
                      color: isSelected ? T.accent : T.text1,
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 6
                    }}
                  >
                    {isSelected && <Check size={12} />}
                    {opt}
                  </motion.button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Card-level search box — full width, below the groups. Typing here and
          pressing Enter submits immediately through the same dedicated handler
          used by the "Find Products" button, folding in any chips already
          selected above. */}
            {showSearch && (

        <div style={{ marginTop: 20 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: T.text2, marginBottom: 10, textTransform: "uppercase" }}>
            Or search directly
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "12px 16px",
              borderRadius: 14,
              background: "rgba(255, 255, 255, 0.04)",
              border: `1px solid ${T.border}`,
            }}
          >
            <Search size={16} opacity={0.5} color="#fff" />
            <input
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              placeholder={card.search_placeholder || "Search here..."}
              style={{
                background: "transparent",
                border: "none",
                outline: "none",
                color: "#fff",
                fontSize: 14,
                fontWeight: 600,
                width: "100%",
              }}
            />
          </div>
        </div>
      )}

      <motion.button
        whileHover={{ scale: 1.02, boxShadow: `0 0 20px ${T.accent}40` }}
        whileTap={{ scale: 0.98 }}
        onClick={handleSubmit}
        style={{
          width: "100%",
          marginTop: 24,
          padding: "16px",
          borderRadius: 16,
          background: `linear-gradient(135deg, ${T.accent}, ${T.indigo})`,
          border: "none",
          color: "#fff",
          fontSize: 15,
          fontWeight: 800,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8
        }}
      >
        {card.submit_button || "Find Products"}
        <ArrowRight size={18} />
      </motion.button>
    </div>
  );
}

function RecommendationCard({ card }: { card: Card }) {
  return (
    <div style={{ 
      background: `linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1))`, 
      border: `1px solid ${T.accent}30`, 
      borderRadius: 24, 
      padding: 24,
      position: "relative",
      overflow: "hidden",
      width: "100%",
      maxWidth: "900px",
      minWidth: 0,
      boxSizing: "border-box",
    }}>
      <div style={{ position: "absolute", top: -20, right: -20, opacity: 0.05 }}>
        <Sparkles size={120} color={T.accent} />
      </div>
      
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <TrendingUp size={16} color={T.accent} />
        <span style={{ fontSize: 12, fontWeight: 800, color: T.accent, textTransform: "uppercase", letterSpacing: "1px" }}>Expert Recommendation</span>
      </div>

      <div style={{ fontSize: 20, fontWeight: 800, color: "#fff", marginBottom: 8 }}>{card.title}</div>
      <div style={{ fontSize: 14, color: T.text1, lineHeight: 1.6 }}>{card.description}</div>
      
      <div style={{ display: "flex", gap: 12, marginTop: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: T.text2 }}>
          <ShieldCheck size={14} color={T.accent} />
          Best Value
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: T.text2 }}>
          <Zap size={14} color={T.gold} />
          Top Performance
        </div>
      </div>
    </div>
  );
}

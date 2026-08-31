import { ChevronLeft, ChevronRight, Clock, Search } from "lucide-react";
import { T } from "@/styles/theme";
import RoboIcon from "@/components/common/RoboIcon";
import type { SessionEntry } from "@/types";
export default function RecentSearchSidebar({
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
                <RoboIcon size={20} />
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

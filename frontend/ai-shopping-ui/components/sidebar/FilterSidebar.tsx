import { useEffect, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Plus,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";

import { T } from "@/styles/theme";
import { filterColor } from "@/lib/filterColor";
export default function FilterSidebar({
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
    const resetId = window.setTimeout(() => {
      setSelected({})
      setCustomInputs({})
      setShowCustomInput({})
    }, 0)

    return () => window.clearTimeout(resetId)
  }, [dynamicFilters])

  // Toggles a single chip value on/off within its filter group.
  const toggle = (group: string, value: string) => {
    setSelected((prev) => {
      const next = { ...prev }
      const groupSet = new Set(prev[group] || [])
      if (groupSet.has(value)) {
        groupSet.delete(value)
      } else {
        groupSet.add(value)
      }
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

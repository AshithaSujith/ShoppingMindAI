"use client"

import React from "react";
import { T } from "@/styles/theme";
import { QUICKCHIPS } from "@/lib/constants";
import { motion, Variants } from "framer-motion";
import {
  ArrowRight,
  Smartphone,
  Headphones,
  Laptop,
  Watch,
} from "lucide-react";

interface WelcomeScreenProps {
  handleSend: (text: string) => void;
}

export default function WelcomeScreen({
  handleSend,
}: WelcomeScreenProps) {
  const getIcon = (label: string) => {
    const lowLabel = label.toLowerCase();
    if (lowLabel.includes("iphone")) return Smartphone;
    if (lowLabel.includes("sony") || lowLabel.includes("boat")) return Headphones;
    if (lowLabel.includes("laptop")) return Laptop;
    if (lowLabel.includes("watch")) return Watch;
    return Smartphone;
  };

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.08 } },
  };

  const itemVariants: Variants = {
    hidden: { y: 16, opacity: 0 },
    visible: { y: 0, opacity: 1, transition: { duration: 0.4, ease: "easeOut" as any } },
  };

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0, // lets this shrink inside the flex parent instead of clipping
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "32px 24px",
        textAlign: "center",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Robot, positioned right, full color, no glow/dim */}
      <motion.div
        initial={{ opacity: 0, x: 60 }}
        animate={{ opacity: 2, x: 0 }}
        transition={{ duration: 0.9, ease: "easeOut" as any }}
        style={{
          position: "absolute",
          right: "1%",
          bottom: "2%",       // anchor to bottom instead of vertical-centering
          height: "100%",       // smaller % so full figure (head to feet) fits with room to spare
          pointerEvents: "none",
          zIndex: 0,
        }}
      >
        <img
          src="/robot-mascot.png"
          alt="Robot"
          style={{
            height: "100%",
            width: "auto",
            maxWidth: "38vw",
            objectFit: "contain",
          }}
        />
      </motion.div>
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        style={{ position: "relative", zIndex: 1, maxWidth: 600 }}
      >
        <motion.h1
          variants={itemVariants}
          style={{
            fontSize: "clamp(30px, 4.4vw, 48px)",
            fontWeight: 900,
            color: "#fff",
            lineHeight: 1.15,
            marginBottom: 16,
            letterSpacing: "-1px",
          }}
        >
          Find the Perfect Product
          <span
            style={{
              background: `linear-gradient(135deg, ${T.accent}, ${T.indigo})`,
              WebkitBackgroundClip: "text" as any,
              WebkitTextFillColor: "transparent" as any,
            }}
          >
            In Seconds.
          </span>
        </motion.h1>

        <motion.p
          variants={itemVariants}
          style={{ fontSize: 17, color: T.text1, marginBottom: 28, lineHeight: 1.6 }}
        >
          Your AI shopping consultant that compares prices, reads reviews, and finds the best deals for you.
        </motion.p>

        <motion.div
          variants={itemVariants}
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(220px, 1fr))",
            gap: 14,
            width: "100%",
          }}
        >
          {QUICKCHIPS.slice(0, 4).map((chip, i) => {
            const Icon = chip.icon || getIcon(chip.label);
            const col = chip.from;

            return (
              <motion.button
                key={i}
                whileHover={{ scale: 1.02, background: "rgba(255, 255, 255, 0.05)" }}
                whileTap={{ scale: 0.98 }}
                onClick={() => handleSend(chip.label)}
                style={{
                  padding: "18px",
                  borderRadius: 22,
                  background: "rgba(255, 255, 255, 0.03)",
                  border: `1px solid ${T.border}`,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  transition: "all 0.2s",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  <div
                    style={{
                      width: 42,
                      height: 42,
                      borderRadius: 14,
                      background: `${col}15`,
                      display: "flex",
                      justifyContent: "center",
                      alignItems: "center",
                      flexShrink: 0,
                      border: `1px solid ${col}30`,
                    }}
                  >
                    <Icon color={col} size={21} />
                  </div>
                  <div style={{ textAlign: "left" }}>
                    <div style={{ fontSize: 15, fontWeight: 700, color: T.text0 }}>{chip.label}</div>
                    <div style={{ marginTop: 2, color: T.text2, fontSize: 12 }}>Find best prices</div>
                  </div>
                </div>
                <ArrowRight color={T.text2} size={17} />
              </motion.button>
            );
          })}
        </motion.div>
      </motion.div>
    </div>
  );
}
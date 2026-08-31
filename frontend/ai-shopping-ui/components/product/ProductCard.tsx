"use client"

import { useState } from "react";
import { ExternalLink, ShoppingBag, Star } from "lucide-react";
import { motion } from "framer-motion";

import { T } from "@/styles/theme";
import { STORECOLORS } from "@/lib/constants";
import type { Product } from "@/types";
import StarRating from "./StarRating";

export default function ProductCard({ product }: { product: Product; key?: string | number }) {
  const [imgError, setImgError] = useState(false)

  const store = product.store || "Unknown"
  const storeColor = STORECOLORS[store.toLowerCase()] || T.accent
  const title = product.productname || product.title || "Product"
  const price = product.priceinr ? product.priceinr.toLocaleString("en-IN") : "NA"

  const origPrice =
    product.originalprice && product.originalprice > (product.priceinr || 0)
      ? product.originalprice.toLocaleString("en-IN")
      : null

  const discount =
    product.discountpercent && product.discountpercent > 0
      ? `${product.discountpercent}% off`
      : null

  const link = product.productlink || product.url

  return (
    <motion.div
      whileHover={{ y: -8 }}
      style={{
        background: "rgba(255, 255, 255, 0.03)",
        backdropFilter: "blur(20px)",
        border: product.isbestprice
          ? `1px solid ${T.gold}88`
          : `1px solid rgba(255, 255, 255, 0.08)`,
        borderRadius: 24,
        display: "flex",
        flexDirection: "column",
        width: 280,
        minWidth: 280,
        maxWidth: 280,
        flexShrink: 0,
        position: "relative",
        overflow: "hidden",
        transition: "all 0.3s ease",
        boxShadow: product.isbestprice 
          ? `0 10px 30px ${T.gold}15` 
          : "0 10px 30px rgba(0, 0, 0, 0.2)",
      }}
    >
      {product.isbestprice && (
        <div style={{
          position: "absolute",
          top: 16,
          right: -34,
          width: 132,
          transform: "rotate(45deg)",
          background: `linear-gradient(135deg, ${T.gold}, ${T.goldDeep})`,
          color: "#000",
          fontSize: 10,
          fontWeight: 900,
          letterSpacing: "0.1em",
          textAlign: "center",
          padding: "6px 0",
          zIndex: 1,
          fontFamily: T.mono,
          boxShadow: "0 2px 10px rgba(0,0,0,0.3)"
        }}>
          BEST DEAL
        </div>
      )}

      <div style={{
        height: 180,
        background: "rgba(255, 255, 255, 0.02)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 20,
        borderBottom: "1px solid rgba(255, 255, 255, 0.05)"
      }}>
        {product.image && !imgError ? (
          <img
            src={product.image}
            alt={title}
            referrerPolicy="no-referrer"
            style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
            onError={() => setImgError(true)}
          />
        ) : (
          <ShoppingBag size={32} color={T.text2} />
        )}
      </div>

      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: storeColor, fontFamily: T.mono, textTransform: "uppercase" }}>
          {store}
        </span>

        <div style={{
          fontSize: 16,
          fontWeight: 700,
          color: "#fff",
          lineHeight: 1.4,
          overflow: "hidden",
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
          minHeight: "2.8em"
        }}>
          {title}
        </div>

        <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
          <span style={{ fontSize: 24, fontWeight: 800, color: "#fff", fontFamily: T.mono }}>₹{price}</span>
          {origPrice && <span style={{ fontSize: 12, color: T.text2, textDecoration: "line-through" }}>₹{origPrice}</span>}
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {discount && (
            <span style={{
              fontSize: 10, fontWeight: 800, color: T.gold, background: `${T.gold}15`,
              padding: "4px 10px", borderRadius: 20, border: `1px solid ${T.gold}30`
            }}>{discount}</span>
          )}
          {(product.rating || 0) > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 4, background: "rgba(255, 255, 255, 0.05)", padding: "4px 10px", borderRadius: 20 }}>
              <Star size={10} fill={T.amber} color={T.amber} />
              <span style={{ fontSize: 11, color: "#fff", fontWeight: 700 }}>{(product.rating || 0).toFixed(1)}</span>
            </div>
          )}
        </div>

        {link && (
          <motion.a
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            href={link}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              background: `linear-gradient(135deg, ${storeColor}, ${storeColor}CC)`,
              borderRadius: 16, padding: "14px", color: "#fff", fontSize: 14, fontWeight: 800,
              textDecoration: "none", marginTop: "auto"
            }}
          >
            Buy on {store} <ExternalLink size={14} />
          </motion.a>
        )}
      </div>
    </motion.div>
  )
}

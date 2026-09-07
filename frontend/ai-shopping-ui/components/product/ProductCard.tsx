"use client"

import { useState } from "react"
import { ExternalLink, Heart, ShoppingBag, Star } from "lucide-react"
import { motion } from "framer-motion"

import { T } from "@/styles/theme"
import { STORECOLORS } from "@/lib/constants"
import type { Product } from "@/types"

type ProductCardProps = {
  product: Product
  onWishlist?: (product: Product) => void
  isWishlisted?: boolean
}

export default function ProductCard({ product, onWishlist, isWishlisted = false }: ProductCardProps) {
  const [imgError, setImgError] = useState(false)
  const store = product.store || "Unknown"
  const storeColor = STORECOLORS[store.toLowerCase()] || T.indigo
  const title = product.productname || product.title || "Product"
  const price = product.priceinr ? product.priceinr.toLocaleString("en-IN") : "NA"
  const origPrice = product.originalprice && product.originalprice > (product.priceinr || 0) ? product.originalprice.toLocaleString("en-IN") : null
  const discount = product.discountpercent && product.discountpercent > 0 ? `${product.discountpercent}% off` : null
  const link = product.productlink || product.url

  return (
    <motion.div whileHover={{ y: -5 }} className="result-product-card" style={{ borderColor: product.isbestprice ? `${T.gold}99` : undefined }}>
      {product.isbestprice && <div className="result-ribbon">BEST DEAL</div>}
      <button type="button" className={`wishlist-button ${isWishlisted ? "is-wishlisted" : ""}`} aria-label={isWishlisted ? `Remove ${title} from wishlist` : `Add ${title} to wishlist`} onClick={() => onWishlist?.(product)}>
        <Heart size={16} fill={isWishlisted ? "currentColor" : "none"} />
      </button>
      <div className="result-image">
        {product.image && !imgError ? <img src={product.image} alt={title} referrerPolicy="no-referrer" onError={() => setImgError(true)} /> : <ShoppingBag size={34} color="#a0a3b2" />}
      </div>
      <div className="result-body">
        <span className="result-store" style={{ color: storeColor }}>{store}</span>
        <div className="result-title">{title}</div>
        <div className="result-price-row"><strong>₹{price}</strong>{origPrice && <del>₹{origPrice}</del>}</div>
        <div className="result-badges">
          {discount && <span className="result-discount">{discount}</span>}
          {(product.rating || 0) > 0 && <span className="result-rating"><Star size={11} fill={T.amber} color={T.amber} />{(product.rating || 0).toFixed(1)}</span>}
        </div>
        {link && <motion.a whileTap={{ scale: .98 }} href={link} target="_blank" rel="noopener noreferrer" className="result-buy" style={{ background: `linear-gradient(100deg, ${storeColor}, ${storeColor}cc)` }}>Buy on {store}<ExternalLink size={13} /></motion.a>}
      </div>
    </motion.div>
  )
}

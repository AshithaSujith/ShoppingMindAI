"use client"

import {
  ArrowRight,
  BadgePercent,
  BarChart3,
  Headphones,
  Laptop,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Star,
  Tag,
  Users,
  Zap,
} from "lucide-react"
import { motion } from "framer-motion"

type WelcomeScreenProps = { handleSend: (text: string) => void }

type SearchTile = { label: string; price: string; icon: typeof Smartphone; image: string; tone: string }

const searchTiles: SearchTile[] = [
  { label: "iPhone 15", price: "From ₹64,999", icon: Smartphone, image: "/iphone-15.png", tone: "#e8f7f0" },
  { label: "boAt Headphones", price: "From ₹1,299", icon: Headphones, image: "/black-headphones.webp", tone: "#f1e8ff" },
  { label: "Gaming Laptops under ₹60K", price: "From ₹45,990", icon: Laptop, image: "/gaming-laptop.webp", tone: "#ebeafe" },
  { label: "Sony WH-1000XM5", price: "From ₹24,990", icon: Headphones, image: "/black-headphones.webp", tone: "#fff1de" },
]

const features = [
  { title: "Compare Prices", subtitle: "Across top stores", query: "Compare prices across Amazon Flipkart Croma Reliance Digital and Tata CLiQ", icon: Tag, tone: "#ffe1db", color: "#f26d66" },
  { title: "Read Reviews", subtitle: "Real user insights", query: "Find the best rated products with reviews", icon: Star, tone: "#eee2ff", color: "#8a5ae9" },
  { title: "Best Deals", subtitle: "Handpicked for you", query: "Show me today's best shopping deals", icon: BadgePercent, tone: "#ddf6df", color: "#42ad6b" },
  { title: "Trusted Results", subtitle: "Accurate & reliable", query: "Find reliable products with good ratings and delivery", icon: ShieldCheck, tone: "#e4ecff", color: "#5572dd" },
]

function SearchArt({ Icon, image }: { Icon: typeof Smartphone; image?: string }) {
  return (
    <div className="search-art">
      {image ? <img src={image} alt="" /> : <Icon />}
    </div>
  )
}

export default function WelcomeScreen({ handleSend }: WelcomeScreenProps) {
  return (
    <div className="home-content">
      <section className="hero-section">
        <div className="hero-copy">
          <motion.h1 initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .45 }}>
            Find the Perfect<br />Product <span className="gradient-text">In Seconds.</span>
          </motion.h1>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: .1, duration: .45 }}>
            Your AI shopping consultant that compares prices,<br className="desktop-break" /> reads reviews, and finds the best deals for you.
          </motion.p>
          <motion.div className="feature-row" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: .16, duration: .45 }}>
            {features.map(({ title, subtitle, query, icon: Icon, tone, color }) => (
              <button type="button" className="feature-tile" key={title} onClick={() => handleSend(query)}>
                <div className="feature-icon" style={{ background: tone, color }}><Icon /></div>
                <div><strong>{title}</strong><small>{subtitle}</small></div>
              </button>
            ))}
          </motion.div>
        </div>

        <div className="hero-decor one"><Sparkles size={30} /></div>
        <div className="hero-decor two"><Tag size={31} /></div>
        <div className="hero-decor three"><ShoppingCartDecor /></div>
        <img className="hero-robot" src="/robot-reference.png" alt="Ottixhow shopping assistant robot" />
        <div className="robot-bubble"><strong>Hi! 👋</strong>I’ll find the best<br />deal for you!</div>
      </section>

      <section className="dashboard-grid">
        <div className="panel popular-panel">
          <div className="panel-heading"><h2><span aria-hidden="true">🔥</span> Popular Searches</h2><button type="button" aria-label="See more searches"><ArrowRight size={17} /></button></div>
          <div className="search-carousel">
            {searchTiles.map(({ label, price, icon: Icon, image, tone }) => (
              <button type="button" className="search-card" key={label} onClick={() => handleSend(label)}>
                <div style={{ color: tone === "#e8f7f0" ? "#227e6a" : tone === "#f1e8ff" ? "#8264c7" : tone === "#ebeafe" ? "#525bbd" : "#ad6c2b" }}><SearchArt Icon={Icon} image={image} /></div>
                <strong>{label}</strong>
                <span>{price}</span>
                <span className="search-arrow"><ArrowRight /></span>
              </button>
            ))}
          </div>
          <div className="carousel-dots" aria-hidden="true"><span /><span /><span /></div>
        </div>

        <div className="panel deal-panel">
          <div className="panel-heading deal-heading"><h2><Zap size={19} /> Today’s Top Deal</h2></div>
          <div className="deal-card">
            <h3>Noise ColorFit Pro 4</h3>
            <p>Smartwatch</p>
            <div className="deal-price"><strong>₹2,499</strong><del>₹4,999</del><span className="deal-percent">50% OFF</span></div>
            <WatchDealArt />
          </div>
          <button type="button" className="deal-button" onClick={() => handleSend("Noise ColorFit Pro 4 smartwatch deal")}><span>View Deal</span><ArrowRight size={18} /></button>
        </div>
      </section>

      <section className="panel stat-strip">
        <Stat icon={BarChart3} tone="#ddf6df" color="#45ad6c" value="1M+" label="Products Compared" />
        <Stat icon={Users} tone="#eadcff" color="#9a5be4" value="500K+" label="Happy Shoppers" />
        <Stat icon={Star} tone="#fff0c9" color="#efa940" value="4.8 ★" label="User Rating" />
        <Stat icon={Zap} tone="#e1e8ff" color="#6076df" value="Real-time" label="Price Updates" />
      </section>
    </div>
  )
}

function Stat({ icon: Icon, tone, color, value, label }: { icon: typeof BarChart3; tone: string; color: string; value: string; label: string }) {
  return <div className="stat-item"><div className="stat-icon" style={{ background: tone, color }}><Icon /></div><div className="stat-copy"><strong>{value}</strong><span>{label}</span></div></div>
}

function WatchDealArt() {
  return <img className="deal-watch" src="/noise-smartwatch.webp" alt="Noise ColorFit Pro 4 smartwatch" />
}

function ShoppingCartDecor() {
  return <div style={{ display: "flex", gap: 4, alignItems: "flex-end" }}><span style={{ display: "block", width: 23, height: 17, border: "2px solid currentColor", borderTop: 0, transform: "skew(-14deg)" }} /><span style={{ width: 5, height: 5, borderRadius: "50%", background: "currentColor" }} /><span style={{ width: 5, height: 5, borderRadius: "50%", background: "currentColor" }} /></div>
}


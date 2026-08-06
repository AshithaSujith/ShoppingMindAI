import { T } from "@/styles/theme";
import {
  Headphones,
  Laptop,
  type LucideIcon,
  Music2,
  Smartphone,
  Watch,
} from "lucide-react";

// Suggested search chips shown on the empty/home state.
export const QUICKCHIPS: { icon: LucideIcon; label: string; from: string; to: string }[] = [
  { icon: Smartphone, label: "iPhone 15", from: "#12A594", to: "#0B7D71" },
  { icon: Headphones, label: "Sony WH-1000XM5", from: "#8FC4F0", to: "#5B8FC9" },
  { icon: Music2, label: "boAt Headphones", from: "#F2A6CB", to: "#D9679F" },
  { icon: Laptop, label: "Gaming Laptop under ₹60K", from: "#FB7185", to: "#C43F52" },
  { icon: Watch, label: "Smartwatch under ₹5K", from: "#E7A93D", to: "#C9861F" },
];

// Brand colors used to tint the "STORE" label and the "View on <store>" button
// per retailer, so Amazon/Flipkart/Myntra are visually distinguishable.
export const STORECOLORS: Record<string, string> = {
  amazon: "#FF9900",
  flipkart: "#2874F0",
  myntra: "#FF3F6C",
};

// Rotating palette used to color-code dynamic filter groups and quick chips,
// so each group/chip gets a different accent color in sequence.
export const FILTERCOLORS: string[] = [T.accent, T.pink, T.sky, T.coral, T.amber];
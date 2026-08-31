import { Star } from "lucide-react";
import { T } from "@/styles/theme";
export default function StarRating({ rating }: { rating: number }) {
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
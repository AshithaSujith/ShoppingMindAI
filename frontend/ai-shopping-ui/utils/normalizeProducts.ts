import type { Product } from "@/types/index";

export const normalizeProducts = (
  rawProducts: Record<string, unknown>[]
): Product[] =>
  rawProducts.map((p) => ({
    ...(p as Record<string, unknown>),
    priceinr: (p as any).priceinr ?? (p as any).price_inr,
    originalprice: (p as any).originalprice ?? (p as any).original_price,
    discountpercent:
      (p as any).discountpercent ??
      (p as any).discount_percent,
    productname:
      (p as any).productname ??
      (p as any).product_name,
    productlink:
      (p as any).productlink ??
      (p as any).product_link,
    reviewcount:
      (p as any).reviewcount ??
      (p as any).review_count,
    deliverylabel:
      (p as any).deliverylabel ??
      (p as any).delivery_label,
    isbestprice:
      (p as any).isbestprice ??
      (p as any).is_best_price,
    isreliable:
      (p as any).isreliable ??
      (p as any).is_reliable,
  }));
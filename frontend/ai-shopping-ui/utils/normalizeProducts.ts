import type { Product } from "@/types/index";

const toNumber = (value: unknown): number | undefined => {
  if (value === null || value === undefined || value === "") return undefined;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : undefined;
};

export const normalizeProducts = (
  rawProducts: Record<string, unknown>[]
): Product[] =>
  rawProducts.map((product) => {
    const value = (camelCase: string, snakeCase: string) =>
      product[camelCase] ?? product[snakeCase]

    return {
      ...product,
      priceinr: toNumber(value("priceinr", "price_inr")),
      originalprice: toNumber(value("originalprice", "original_price")),
      discountpercent: toNumber(value("discountpercent", "discount_percent")),
      productname: value("productname", "product_name") as string | undefined,
      productlink: value("productlink", "product_link") as string | undefined,
      reviewcount: toNumber(value("reviewcount", "review_count")),
      rating: toNumber(product.rating),
      deliverylabel: value("deliverylabel", "delivery_label") as string | undefined,
      isbestprice: Boolean(value("isbestprice", "is_best_price")),
      isreliable: Boolean(value("isreliable", "is_reliable")),
    }
  });

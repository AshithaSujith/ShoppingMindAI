import type {
  BackendResponse,
  CanonicalProduct,
} from "@/types";

const BASE_URL = "http://127.0.0.1:8000";

export async function searchProducts(
  query: string,
  sessionId: string
): Promise<BackendResponse> {
  const response = await fetch(`${BASE_URL}/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      query,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    throw new Error("Search request failed");
  }

  return response.json();
}

export async function scrapeProducts(
  searchQuery: string,
  canonicalProduct: CanonicalProduct
): Promise<BackendResponse> {
  const response = await fetch(`${BASE_URL}/scrape`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      search_query: searchQuery,
      canonical_product: canonicalProduct,
    }),
  });

  if (!response.ok) {
    throw new Error("Scrape request failed");
  }

  return response.json();
}
import type { BackendResponse, CanonicalProduct } from "@/types";

// Use the Next.js same-origin proxy by default.
// Set NEXT_PUBLIC_API_URL only when calling the FastAPI server directly.
const BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "/api").replace(/\/$/, "");

type ErrorPayload = {
  message?: unknown;
  detail?: unknown;
  error?: unknown;
};

function getErrorMessage(payload: ErrorPayload | null, fallback: string): string {
  const value = payload?.detail ?? payload?.message ?? payload?.error;

  if (typeof value === "string" && value.trim()) {
    return value;
  }

  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg?: unknown }).msg ?? "Validation error");
        }
        return JSON.stringify(item);
      })
      .join(", ");
  }

  return fallback;
}

async function parseResponse(response: Response): Promise<BackendResponse> {
  const rawBody = await response.text();
  let payload: BackendResponse & ErrorPayload | null = null;

  if (rawBody.trim()) {
    try {
      payload = JSON.parse(rawBody) as BackendResponse & ErrorPayload;
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const fallback = rawBody.trim()
      ? rawBody.slice(0, 500)
      : `Request failed with status ${response.status}`;

    console.error("Backend request failed", {
      url: response.url,
      status: response.status,
      statusText: response.statusText,
      body: rawBody,
    });

    throw new Error(getErrorMessage(payload, fallback));
  }

  if (!payload) {
    throw new Error("The backend returned an empty or invalid response.");
  }

  return payload;
}

async function request(url: string, options?: RequestInit): Promise<BackendResponse> {
  try {
    const response = await fetch(url, options);
    return await parseResponse(response);
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }

    throw new Error("Unable to connect to the backend.");
  }
}

export async function searchProducts(
  query: string,
  sessionId: string,
  filters?: Record<string, string[]>,
): Promise<BackendResponse> {
  return request(`${BASE_URL}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query,
      session_id: sessionId,
      ...(filters ? { filters } : {}),
    }),
    signal: AbortSignal.timeout(120_000),
  });
}

export async function scrapeProducts(
  searchQuery: string,
  canonicalProduct: CanonicalProduct,
): Promise<BackendResponse> {
  return request(`${BASE_URL}/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      search_query: searchQuery,
      canonical_product: canonicalProduct,
    }),
    signal: AbortSignal.timeout(180_000),
  });
}

export async function clearSession(sessionId: string): Promise<void> {
  await request(`${BASE_URL}/session/clear`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
    signal: AbortSignal.timeout(15_000),
  });
}

export async function getSessionHistory(sessionId: string): Promise<BackendResponse> {
  return request(`${BASE_URL}/session/history/${encodeURIComponent(sessionId)}`, {
    method: "GET",
    headers: { "Accept": "application/json" },
    signal: AbortSignal.timeout(15_000),
  });
}

export type WishlistItem = {
  id: number;
  product: Record<string, unknown>;
};

type WishlistResponse = BackendResponse & { items?: WishlistItem[] };

export async function listWishlist(sessionId: string): Promise<{ items: WishlistItem[] }> {
  const response = (await request(
    `${BASE_URL}/wishlist/${encodeURIComponent(sessionId)}`,
    { signal: AbortSignal.timeout(15_000) },
  )) as WishlistResponse;

  return {
    items: Array.isArray(response.items) ? response.items : [],
  };
}

export async function addWishlist(
  sessionId: string,
  product: Record<string, unknown>,
): Promise<void> {
  await request(`${BASE_URL}/wishlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, product }),
    signal: AbortSignal.timeout(15_000),
  });
}

export async function removeWishlist(sessionId: string, itemId: number): Promise<void> {
  await request(
    `${BASE_URL}/wishlist/${encodeURIComponent(sessionId)}/${itemId}`,
    {
      method: "DELETE",
      signal: AbortSignal.timeout(15_000),
    },
  );
}

export type PriceAlert = {
  id: number;
  search_query: string;
  target_price: number | null;
  active: boolean;
};

type PriceAlertResponse = BackendResponse & { alerts?: PriceAlert[]; alert?: PriceAlert };

export async function listPriceAlerts(sessionId: string): Promise<{ alerts: PriceAlert[] }> {
  const response = (await request(
    `${BASE_URL}/alerts/${encodeURIComponent(sessionId)}`,
    { signal: AbortSignal.timeout(15_000) },
  )) as PriceAlertResponse;

  return {
    alerts: Array.isArray(response.alerts) ? response.alerts : [],
  };
}

export async function createPriceAlert(
  sessionId: string,
  searchQuery: string,
  targetPrice?: number,
): Promise<{ alert: PriceAlert }> {
  const response = await request(`${BASE_URL}/alerts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      search_query: searchQuery,
      target_price: targetPrice ?? null,
    }),
    signal: AbortSignal.timeout(15_000),
  });

  const alert = (response as PriceAlertResponse).alert;
  if (!alert) {
    throw new Error("The backend did not return the created price alert.");
  }

  return { alert };
}

export async function deletePriceAlert(
  sessionId: string,
  alertId: number,
): Promise<void> {
  await request(
    `${BASE_URL}/alerts/${encodeURIComponent(sessionId)}/${alertId}`,
    {
      method: "DELETE",
      signal: AbortSignal.timeout(15_000),
    },
  );
}

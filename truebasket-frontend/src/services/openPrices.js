/**
 * Open Prices (https://prices.openfoodfacts.org) — real, community-submitted
 * shop prices, each backed by a photo of a price tag or receipt.
 * Coverage varies a lot by country; many Indian products have none yet.
 */
import { fetchJson } from "../lib/http.js";

const BASE = (import.meta.env.VITE_OPEN_PRICES_URL || "https://prices.openfoodfacts.org").replace(/\/+$/, "");

function hostOf(url) {
  try {
    return url ? new URL(url).hostname.replace(/^www\./, "") : null;
  } catch {
    return null;
  }
}

export async function getCommunityPrices(code, { signal } = {}) {
  const params = new URLSearchParams({ product_code: code, order_by: "-date", size: "20" });
  const data = await fetchJson(`${BASE}/api/v1/prices?${params}`, { signal, source: "Open Prices" });
  return (data.items || []).map((p) => ({
    id: p.id,
    price: typeof p.price === "number" ? p.price : Number(p.price),
    currency: p.currency || null,
    date: p.date || null,
    discounted: Boolean(p.price_is_discounted),
    priceWithoutDiscount: p.price_without_discount ?? null,
    store: p.location?.osm_name || hostOf(p.location?.website_url),
    city: p.location?.osm_address_city || null,
    country: p.location?.osm_address_country || null,
    online: p.location?.type === "ONLINE",
    proofType: p.proof?.type || null,
  })).filter((p) => Number.isFinite(p.price));
}

export const pricesPageUrl = (code) => `${BASE}/products/${encodeURIComponent(code)}`;

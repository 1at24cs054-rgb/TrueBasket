/**
 * Optional live price feed from your own backend.
 *
 * Retailers don't publish public price APIs, so live prices need an authorised
 * source (partner/affiliate feed or a data provider you have rights to use),
 * served by your backend. Set VITE_PRICE_API_URL to enable it.
 *
 * GET {VITE_PRICE_API_URL}/api/prices?barcode=…&query=…&pincode=…
 * → { "listings": [ { "retailer_id": "blinkit", "retailer": "Blinkit",
 *       "price_inr": 349, "mrp_inr": 399, "pack_size": { "value": 500, "unit": "g" },
 *       "in_stock": true, "url": "https://…", "checked_at": "ISO-8601" } ] }
 */
import { fetchJson } from "../lib/http.js";

const BASE = (import.meta.env.VITE_PRICE_API_URL !== undefined ? import.meta.env.VITE_PRICE_API_URL : (import.meta.env.VITE_API_URL || "")).replace(/\/+$/, "");

export const priceFeedEnabled = import.meta.env.VITE_PRICE_API_URL !== "disabled";

export async function getLivePrices({ barcode, query, pincode }, { signal } = {}) {
  if (!priceFeedEnabled) return null;
  const params = new URLSearchParams();
  if (barcode) params.set("barcode", barcode);
  if (query) params.set("query", query);
  if (pincode) params.set("pincode", pincode);
  const data = await fetchJson(`${BASE}/api/prices?${params}`, { signal, source: "TrueBasket price service", timeoutMs: 30000 });
  return (data.listings || []).filter((l) => typeof l.price_inr === "number");
}

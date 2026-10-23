/**
 * Best known price for a product, from:
 *  - prices the user typed on Where to buy (saved per barcode on this device)
 *  - the live price service, when VITE_PRICE_API_URL is configured
 * Returns null when nothing is known — never an estimate.
 */
import { RETAILERS } from "../config/retailers.js";
import { isNum, perHundred } from "./format.js";

function readMine(code) {
  try {
    return JSON.parse(localStorage.getItem(`tb:prices:${code}`) || "{}") || {};
  } catch {
    return {};
  }
}

export function offersFor(product, liveListings = []) {
  const out = [];
  const mine = readMine(product.code);
  for (const r of RETAILERS) {
    const e = mine[r.id];
    if (!e || e.price === "" || e.price === undefined) continue;
    const price = Number(e.price);
    const size = e.size ? Number(e.size) : product.pack?.value ?? null;
    if (isNum(price) && price > 0) out.push({ retailer: r.name, price, size, per100: perHundred(price, size ? { value: size } : null), source: "you" });
  }
  for (const l of liveListings || []) {
    const size = l.pack_size?.value ?? product.pack?.value ?? null;
    if (isNum(l.price_inr)) out.push({ retailer: l.retailer, price: l.price_inr, size, per100: perHundred(l.price_inr, size ? { value: size } : null), source: "live", url: l.url });
  }
  return out;
}

/** Cheapest offer, by price per 100 g when known, otherwise by pack price. */
export function bestOffer(offers) {
  if (!offers.length) return null;
  const withUnit = offers.filter((o) => isNum(o.per100));
  if (withUnit.length) return [...withUnit].sort((a, b) => a.per100 - b.per100)[0];
  return [...offers].sort((a, b) => a.price - b.price)[0];
}

/** Pack-size buckets used by search filters (grams or ml). */
export const SIZE_BUCKETS = [
  { id: "s", label: "Up to 250 g", test: (v) => v <= 250 },
  { id: "m", label: "251 – 500 g", test: (v) => v > 250 && v <= 500 },
  { id: "l", label: "501 g – 1 kg", test: (v) => v > 500 && v <= 1000 },
  { id: "xl", label: "Over 1 kg", test: (v) => v > 1000 },
];

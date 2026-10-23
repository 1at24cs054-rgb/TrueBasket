/**
 * Indian grocery and quick-commerce retailers.
 *
 * None of these publish a public price API, and prices depend on your pincode,
 * so TrueBasket opens each retailer's own product search instead of guessing a
 * price. If a search URL format changes, update it here.
 */
export const RETAILERS = [
  { id: "blinkit", name: "Blinkit", kind: "Quick commerce", eta: "10–20 min", color: "#f8cb46", search: (q) => `https://blinkit.com/s/?q=${encodeURIComponent(q)}` },
  { id: "instamart", name: "Swiggy Instamart", kind: "Quick commerce", eta: "10–30 min", color: "#fc8019", search: (q) => `https://www.swiggy.com/instamart/search?custom_back=true&query=${encodeURIComponent(q)}` },
  { id: "zepto", name: "Zepto", kind: "Quick commerce", eta: "10–20 min", color: "#5b2a86", search: (q) => `https://www.zeptonow.com/search?query=${encodeURIComponent(q)}` },
  { id: "bigbasket", name: "BigBasket", kind: "Online grocery", eta: "Same / next day", color: "#84c225", search: (q) => `https://www.bigbasket.com/ps/?q=${encodeURIComponent(q)}` },
  { id: "dmart", name: "DMart Ready", kind: "Online grocery", eta: "Next day / pickup", color: "#00843d", search: (q) => `https://www.dmart.in/search?searchTerm=${encodeURIComponent(q)}` },
  { id: "jiomart", name: "JioMart", kind: "Online grocery", eta: "Same / next day", color: "#0a5bd3", search: (q) => `https://www.jiomart.com/search/${encodeURIComponent(q)}` },
  { id: "amazon", name: "Amazon India", kind: "Marketplace", eta: "1–3 days", color: "#232f3e", search: (q) => `https://www.amazon.in/s?k=${encodeURIComponent(q)}` },
  { id: "flipkart", name: "Flipkart", kind: "Marketplace", eta: "1–3 days", color: "#2874f0", search: (q) => `https://www.flipkart.com/search?q=${encodeURIComponent(q)}` },
];

/** Best search phrase for a retailer: brand + name + pack size. */
export function retailerQuery(product, { withSize = true } = {}) {
  return [product?.brand, product?.name, withSize ? product?.quantity : null].filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
}

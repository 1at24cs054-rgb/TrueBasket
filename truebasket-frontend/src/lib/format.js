/** Display helpers. These only format returned values — they never invent them. */

export const isNum = (v) => typeof v === "number" && Number.isFinite(v);

const inr0 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function formatINR(value, { precise = false } = {}) {
  if (!isNum(value)) return null;
  return (precise || !Number.isInteger(value) ? inr2 : inr0).format(value);
}

export function formatMoney(value, currency) {
  if (!isNum(value)) return null;
  try {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: currency || "INR", minimumFractionDigits: Number.isInteger(value) ? 0 : 2, maximumFractionDigits: 2 }).format(value);
  } catch {
    return `${value} ${currency || ""}`.trim();
  }
}

export function formatPack(pack) {
  if (!pack || !isNum(pack.value)) return null;
  if (pack.unit === "g" && pack.value >= 1000) return `${pack.value / 1000} kg`;
  if (pack.unit === "ml" && pack.value >= 1000) return `${pack.value / 1000} L`;
  return `${pack.value} ${pack.unit}`;
}

/** Price per 100 g/ml — plain arithmetic on a price and a pack size. */
export function perHundred(price, pack) {
  if (!isNum(price) || !pack || !isNum(pack.value) || pack.value <= 0) return null;
  return Math.round((price / pack.value) * 100 * 100) / 100;
}

export function formatPerHundred(value, unit = "g") {
  if (!isNum(value)) return null;
  return `${inr2.format(value)} / 100 ${unit}`;
}

export function formatDate(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function formatBytes(bytes) {
  if (!isNum(bytes)) return "";
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const NUTRIENTS = [
  { key: "energy_kcal", label: "Energy", unit: "kcal" },
  { key: "protein_g", label: "Protein", unit: "g" },
  { key: "carbohydrate_g", label: "Carbohydrates", unit: "g" },
  { key: "total_sugars_g", label: "Total sugars", unit: "g" },
  { key: "added_sugars_g", label: "Added sugars", unit: "g", indent: true },
  { key: "total_fat_g", label: "Total fat", unit: "g" },
  { key: "saturated_fat_g", label: "Saturated fat", unit: "g", indent: true },
  { key: "fibre_g", label: "Fibre", unit: "g" },
  { key: "sodium_mg", label: "Sodium", unit: "mg" },
  { key: "salt_g", label: "Salt", unit: "g" },
];

export function formatNutrient(value, unit) {
  if (!isNum(value)) return null;
  const v = Number.isInteger(value) ? value : value.toFixed(unit === "g" && value < 1 ? 2 : 1).replace(/\.0+$/, "");
  return `${v} ${unit}`;
}


import { Apple, Candy, CircleDot, Droplet, FlaskConical, Leaf, Milk, Nut, Pill, Wheat } from "lucide-react";

/**
 * Plain-language role for an ingredient, from its name only.
 * Deliberately general (e.g. "Sweetener") — never a health verdict.
 */
const RULES = [
  { re: /\b(e ?\d{3}[a-z]?|ins ?\d{3})\b|emulsifier|stabili[sz]er|preservative|colou?r|antioxidant|acidity|raising agent|thickener|flavour enhancer/i, icon: FlaskConical, role: "Food additive", tag: { label: "Additive", tone: "teal" }, tint: "#e2ecea", ink: "#1b655d" },
  { re: /flavou?r/i, icon: FlaskConical, role: "Flavouring", tag: { label: "Flavouring", tone: "slate" }, tint: "#ecebe6", ink: "#5a5f5c" },
  { re: /sugar|syrup|glucose|fructose|dextrose|jaggery|honey|maltodextrin|sucrose|invert/i, icon: Candy, role: "Sweetener", tag: { label: "Added sugar", tone: "clay" }, tint: "#f6e3dc", ink: "#9b3d2b" },
  { re: /palm/i, icon: Droplet, role: "Vegetable fat", tag: { label: "Palm oil", tone: "amber" }, tint: "#fbefd6", ink: "#9a6a12" },
  { re: /\boil\b|fat|butter|ghee|margarine/i, icon: Droplet, role: "Fat or oil", tag: { label: "Fat", tone: "slate" }, tint: "#fbf1dc", ink: "#9a6a12" },
  { re: /salt|sodium chloride/i, icon: CircleDot, role: "Seasoning", tag: { label: "Salt", tone: "slate" }, tint: "#eef0f0", ink: "#5a5f5c" },
  { re: /vitamin|mineral|iron|calcium|zinc|folic|niacin|thiamin|riboflavin/i, icon: Pill, role: "Added for nutrition", tag: { label: "Fortification", tone: "teal" }, tint: "#e3ebf6", ink: "#2b4f7d" },
  { re: /whole ?(grain|wheat|meal)|\boats?\b|millet|ragi|jowar|bajra|quinoa|brown rice|barley/i, icon: Wheat, role: "Grain", tag: { label: "Whole grain", tone: "sage" }, tint: "#eef3e3", ink: "#3f6b35" },
  { re: /wheat|flour|maida|rice|corn|maize|semolina|starch|bran|flakes|cereal/i, icon: Wheat, role: "Grain or starch", tag: null, tint: "#f3ecd9", ink: "#7a5a1c" },
  { re: /milk|whey|cream|cheese|curd|lactose|casein|yogh?urt/i, icon: Milk, role: "Dairy", tag: { label: "Dairy", tone: "slate" }, tint: "#e8f0f3", ink: "#1b655d" },
  { re: /almond|cashew|nut|peanut|groundnut|pistachio|walnut|hazelnut|seed|sesame|flax|chia/i, icon: Nut, role: "Nuts or seeds", tag: null, tint: "#f1e4d2", ink: "#7a4f22" },
  { re: /raisin|fruit|berry|apple|banana|mango|date|fig|apricot|cranberry|papaya|coconut/i, icon: Apple, role: "Fruit", tag: null, tint: "#f6e0dc", ink: "#9b3d2b" },
];

const FALLBACK = { icon: Leaf, role: "Ingredient", tag: null, tint: "#eef3e3", ink: "#3f6b35" };

export function ingredientInfo(text) {
  return RULES.find((r) => r.re.test(text || "")) || FALLBACK;
}

/**
 * Nutrition notes using published per-100 g thresholds:
 * "low/high" claims from EU Regulation 1924/2006, and "high" levels from
 * the UK FSA front-of-pack traffic-light scheme.
 */
export function nutritionInsights(n) {
  if (!n) return [];
  const out = [];
  const has = (v) => typeof v === "number";
  if (has(n.total_sugars_g)) {
    if (n.total_sugars_g <= 5) out.push({ good: true, text: "Low in sugar (≤ 5 g per 100 g)" });
    else if (n.total_sugars_g > 22.5) out.push({ good: false, text: "High in sugar (> 22.5 g per 100 g)" });
  }
  if (has(n.added_sugars_g) && n.added_sugars_g > 0) out.push({ good: false, text: `Contains ${n.added_sugars_g} g added sugar per 100 g` });
  if (has(n.fibre_g)) {
    if (n.fibre_g >= 6) out.push({ good: true, text: "High in fibre (≥ 6 g per 100 g)" });
    else if (n.fibre_g >= 3) out.push({ good: true, text: "Source of fibre (≥ 3 g per 100 g)" });
  }
  if (has(n.protein_g) && has(n.energy_kcal) && n.energy_kcal > 0) {
    const pct = (n.protein_g * 4 * 100) / n.energy_kcal;
    if (pct >= 20) out.push({ good: true, text: "High in protein (≥ 20% of energy)" });
    else if (pct >= 12) out.push({ good: true, text: "Source of protein (≥ 12% of energy)" });
  }
  if (has(n.total_fat_g)) {
    if (n.total_fat_g <= 3) out.push({ good: true, text: "Low in fat (≤ 3 g per 100 g)" });
    else if (n.total_fat_g > 17.5) out.push({ good: false, text: "High in fat (> 17.5 g per 100 g)" });
  }
  if (has(n.saturated_fat_g)) {
    if (n.saturated_fat_g <= 1.5) out.push({ good: true, text: "Low in saturated fat (≤ 1.5 g per 100 g)" });
    else if (n.saturated_fat_g > 5) out.push({ good: false, text: "High in saturated fat (> 5 g per 100 g)" });
  }
  const salt = has(n.salt_g) ? n.salt_g : has(n.sodium_mg) ? (n.sodium_mg * 2.5) / 1000 : null;
  if (salt !== null) {
    if (salt <= 0.3) out.push({ good: true, text: "Low in salt (≤ 0.3 g per 100 g)" });
    else if (salt > 1.5) out.push({ good: false, text: "High in salt (> 1.5 g per 100 g)" });
  }
  return out;
}

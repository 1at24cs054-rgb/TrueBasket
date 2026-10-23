/**
 * Matches the user's avoid list against what the product actually lists:
 * ingredient names (incl. sub-ingredients), allergens and the ingredients text.
 * Simple, explainable text matching — the UI shows exactly what matched.
 */
const norm = (s) => String(s || "").toLowerCase().replace(/^[a-z]{2}:/, "").replace(/[-_]/g, " ").trim();

const SYNONYMS = {
  sugar: ["sugar", "sucrose", "glucose", "fructose", "dextrose", "syrup", "jaggery", "honey"],
  "palm oil": ["palm"],
  gluten: ["gluten", "wheat", "barley", "rye"],
  milk: ["milk", "lactose", "whey", "casein", "butter"],
  soy: ["soy", "soya"],
  peanuts: ["peanut", "groundnut"],
};

function flatten(ings, out = []) {
  for (const i of ings || []) {
    out.push(i.text);
    if (i.sub?.length) flatten(i.sub, out);
  }
  return out;
}

export function matchAvoid(product, avoid = []) {
  if (!product || !avoid.length) return [];
  const haystack = [
    ...flatten(product.ingredients).map(norm),
    ...product.allergens.map(norm),
    ...(product.analysis.includes("en:palm-oil") ? ["palm oil"] : []),
  ];
  const text = norm(product.ingredientsText);
  return avoid
    .map((term) => {
      const t = norm(term);
      const needles = SYNONYMS[t] || [t];
      const hits = [...new Set(haystack.filter((h) => needles.some((n) => h.includes(n))))];
      if (hits.length === 0 && text && needles.some((n) => text.includes(n))) hits.push("ingredients text");
      return { term, hits };
    })
    .filter((m) => m.hits.length > 0);
}

export function ingredientMatchesAvoid(ingText, avoid = []) {
  const h = norm(ingText);
  return avoid.some((term) => (SYNONYMS[norm(term)] || [norm(term)]).some((n) => h.includes(n)));
}

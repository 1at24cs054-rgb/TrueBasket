/**
 * Open Food Facts client — the global, open database of packaged food
 * (https://world.openfoodfacts.org). No API key needed.
 *
 * Fair-use limits (per user/IP): ~15 product reads/min and ~10 searches/min.
 * So: no search-as-you-type, results are cached in memory, and 429/503 is
 * surfaced to the user as "limiting requests".
 *
 * Data is community-contributed. The UI labels it as such and links back to
 * the product page so users can check or correct it.
 */
import { fetchJson, HttpError } from "../lib/http.js";

const BASE = (import.meta.env.VITE_OFF_BASE_URL || "https://world.openfoodfacts.org").replace(/\/+$/, "");
const SRC = "Open Food Facts";

const LIST_FIELDS = [
  "code", "product_name", "product_name_en", "brands", "quantity", "product_quantity", "product_quantity_unit",
  "image_front_small_url", "image_front_url", "image_url", "nutriscore_grade", "nova_group", "categories_tags",
  "countries_tags", "nutriments", "additives_tags", "ingredients_analysis_tags", "allergens_tags",
].join(",");

const PRODUCT_FIELDS = [
  LIST_FIELDS, "generic_name", "generic_name_en", "categories", "categories_hierarchy", "ingredients_text", "ingredients_text_en",
  "ingredients", "traces_tags", "labels_tags", "serving_size", "nutrition_data_per", "no_nutrition_data",
  "image_ingredients_url", "image_nutrition_url", "stores", "countries", "manufacturing_places", "origins",
  "last_modified_t", "completeness",
].join(",");

export const COUNTRIES = [
  { id: "world", label: "Worldwide" },
  { id: "india", label: "India" },
  { id: "united-kingdom", label: "United Kingdom" },
  { id: "united-states", label: "United States" },
  { id: "united-arab-emirates", label: "UAE" },
  { id: "france", label: "France" },
  { id: "germany", label: "Germany" },
];

export const isBarcode = (q) => /^\d{8,14}$/.test(String(q).replace(/\s/g, ""));

export const productUrl = (code) => `${BASE}/product/${encodeURIComponent(code)}`;

// ------------------------------------------------------------------ normalize

const num = (v) => {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : null;
};

const round = (v, d = 1) => (v === null ? null : Math.round(v * 10 ** d) / 10 ** d);

function parsePack(raw) {
  const value = num(raw.product_quantity);
  let unit = (raw.product_quantity_unit || "").toLowerCase();
  if (value && !unit) {
    unit = /\b(ml|l|cl)\b/i.test(raw.quantity || "") ? "ml" : "g";
  }
  if (!value || value <= 0 || !["g", "ml"].includes(unit)) return null;
  return { value, unit };
}

function nutrimentSet(n, suffix) {
  if (!n) return {};
  const pick = (k) => num(n[`${k}_${suffix}`]);
  const sodiumG = pick("sodium");
  let energyKcal = pick("energy-kcal");
  if (energyKcal === null && pick("energy") !== null) energyKcal = round(pick("energy") / 4.184, 0); // kJ → kcal
  return {
    energy_kcal: energyKcal === null ? null : Math.round(energyKcal),
    protein_g: round(pick("proteins")),
    carbohydrate_g: round(pick("carbohydrates")),
    total_sugars_g: round(pick("sugars")),
    added_sugars_g: round(pick("added-sugars")),
    total_fat_g: round(pick("fat")),
    saturated_fat_g: round(pick("saturated-fat")),
    fibre_g: round(pick("fiber")),
    sodium_mg: sodiumG === null ? null : Math.round(sodiumG * 1000),
    salt_g: round(pick("salt"), 2),
  };
}

const firstBrand = (b) => (b ? String(b).split(",")[0].trim() : null);

function normIngredient(i) {
  return {
    id: i.id || null,
    text: (i.text || i.id || "").replace(/_/g, "").trim(),
    percent: num(i.percent), // declared on pack
    percentEstimate: num(i.percent_estimate), // OFF estimate
    vegan: i.vegan || null,
    vegetarian: i.vegetarian || null,
    fromPalmOil: i.from_palm_oil || null,
    sub: Array.isArray(i.ingredients) ? i.ingredients.map(normIngredient) : [],
  };
}

export function normalizeProduct(raw) {
  if (!raw) return null;
  const grade = (raw.nutriscore_grade || "").toLowerCase();
  return {
    code: String(raw.code || ""),
    name: raw.product_name_en || raw.product_name || raw.generic_name_en || raw.generic_name || null,
    brand: firstBrand(raw.brands),
    brands: raw.brands || null,
    quantity: raw.quantity || null,
    pack: parsePack(raw),
    image: raw.image_front_url || raw.image_url || raw.image_front_small_url || null,
    thumb: raw.image_front_small_url || raw.image_front_url || raw.image_url || null,
    imageIngredients: raw.image_ingredients_url || null,
    imageNutrition: raw.image_nutrition_url || null,
    nutriscore: /^[a-e]$/.test(grade) ? grade : null,
    nova: [1, 2, 3, 4].includes(Number(raw.nova_group)) ? Number(raw.nova_group) : null,
    categoriesTags: raw.categories_tags || [],
    categoriesHierarchy: raw.categories_hierarchy || raw.categories_tags || [],
    categoryLabel: raw.categories ? String(raw.categories).split(",").pop().trim() : null,
    countriesTags: raw.countries_tags || [],
    ingredientsText: raw.ingredients_text_en || raw.ingredients_text || null,
    ingredients: Array.isArray(raw.ingredients) ? raw.ingredients.map(normIngredient) : [],
    additives: raw.additives_tags || [],
    allergens: raw.allergens_tags || [],
    traces: raw.traces_tags || [],
    labels: raw.labels_tags || [],
    analysis: raw.ingredients_analysis_tags || [],
    servingSize: raw.serving_size || null,
    noNutritionData: raw.no_nutrition_data === "on",
    per100: nutrimentSet(raw.nutriments, "100g"),
    perServing: nutrimentSet(raw.nutriments, "serving"),
    stores: raw.stores ? String(raw.stores).split(",").map((s) => s.trim()).filter(Boolean) : [],
    origins: raw.origins || null,
    lastModified: raw.last_modified_t ? new Date(raw.last_modified_t * 1000).toISOString() : null,
    sourceUrl: raw.code ? productUrl(raw.code) : null,
    description: raw.generic_name_en || raw.generic_name || null,
    completeness: num(raw.completeness),
  };
}

// ------------------------------------------------------------------ requests

const BACKEND_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

export async function getProduct(code, { signal } = {}) {
  const clean = String(code).replace(/\s/g, "");

  // Try backend proxy first if available
  if (BACKEND_BASE) {
    try {
      const data = await fetchJson(`${BACKEND_BASE}/api/products/barcode/${encodeURIComponent(clean)}`, {
        signal,
        source: "TrueBasket product lookup",
        timeoutMs: 15000,
      });
      if (data?.product) {
        return normalizeProduct({ code: clean, ...data.product });
      }
    } catch (e) {
      if (e.kind === "cancelled" || e.kind === "not_found") throw e;
    }
  }

  const url = `${BASE}/api/v2/product/${encodeURIComponent(clean)}?fields=${PRODUCT_FIELDS}`;
  let data;
  try {
    data = await fetchJson(url, { signal, source: SRC });
  } catch (e) {
    if (e.kind === "not_found") throw new HttpError(`No product with barcode ${clean} is in Open Food Facts yet.`, { kind: "not_found", source: SRC });
    throw e;
  }
  if (!data || data.status === 0 || !data.product) {
    throw new HttpError(`No product with barcode ${clean} is in Open Food Facts yet.`, { kind: "not_found", source: SRC });
  }
  return normalizeProduct({ code: clean, ...data.product });
}

/** Full-text search with resilient backend proxy and Open Food Facts fallback. */
export async function searchProducts(query, { page = 1, pageSize = 24, country = "world", signal } = {}) {
  if (BACKEND_BASE) {
    try {
      const bParams = new URLSearchParams({
        q: query,
        page: String(page),
        page_size: String(pageSize),
      });
      if (country && country !== "world") bParams.set("country", country);
      const data = await fetchJson(`${BACKEND_BASE}/api/products/search?${bParams}`, {
        signal,
        source: "TrueBasket product search",
        timeoutMs: 15000,
      });
      const rawProducts = data.products || data.hits || [];
      const products = rawProducts.map(normalizeProduct).filter((p) => p && p.code && p.name);
      const count = Number(data.count) || products.length;
      return { products, count, page, pageSize, hasMore: page * pageSize < count };
    } catch (e) {
      if (e?.kind === "cancelled") throw e;
    }
  }

  const params = new URLSearchParams({
    search_terms: query,
    search_simple: "1",
    action: "process",
    json: "1",
    page: String(page),
    page_size: String(pageSize),
    sort_by: "unique_scans_n",
    fields: LIST_FIELDS,
  });
  if (country && country !== "world") {
    params.set("tagtype_0", "countries");
    params.set("tag_contains_0", "contains");
    params.set("tag_0", country);
  }
  const data = await fetchJson(`${BASE}/cgi/search.pl?${params}`, { signal, source: SRC });
  const products = (data.products || []).map(normalizeProduct).filter((p) => p.code && p.name);
  const count = Number(data.count) || 0;
  return { products, count, page, pageSize, hasMore: page * pageSize < count };
}

/** Products in the same category (most specific first, broadening if too few). */
export async function getAlternatives(product, { country = "world", signal } = {}) {
  const cats = [...(product.categoriesHierarchy || [])].filter((c) => c.startsWith("en:")).reverse();
  if (cats.length === 0) return { products: [], category: null };

  let best = { products: [], category: cats[0] };

  if (BACKEND_BASE) {
    try {
      for (const cat of cats.slice(0, 3)) {
        const bParams = new URLSearchParams({
          categories_tags: cat,
          page_size: "40",
        });
        if (country && country !== "world") bParams.set("country", country);
        const data = await fetchJson(`${BACKEND_BASE}/api/products/alternatives?${bParams}`, {
          signal,
          source: "TrueBasket alternatives",
          timeoutMs: 15000,
        });
        const products = (data.products || [])
          .map(normalizeProduct)
          .filter((p) => p && p.code && p.code !== product.code && p.name && Object.values(p.per100).some((v) => v !== null));
        if (products.length > best.products.length) best = { products, category: cat };
        if (products.length >= 4) break;
      }
      if (best.products.length > 0) return best;
    } catch (e) {
      if (e?.kind === "cancelled") throw e;
    }
  }

  for (const cat of cats.slice(0, 3)) {
    const params = new URLSearchParams({
      categories_tags: cat,
      fields: LIST_FIELDS,
      page_size: "40",
      sort_by: "popularity_key",
    });
    if (country && country !== "world") params.set("countries_tags", `en:${country}`);
    const data = await fetchJson(`${BASE}/api/v2/search?${params}`, { signal, source: SRC });
    const products = (data.products || [])
      .map(normalizeProduct)
      .filter((p) => p.code && p.code !== product.code && p.name && Object.values(p.per100).some((v) => v !== null));
    if (products.length > best.products.length) best = { products, category: cat };
    if (products.length >= 4) break; // enough; don't spend more of the search rate limit
  }
  return best;
}


// ------------------------------------------------------------------ taxonomy

let additivesPromise = null;

/** Lazily loads the OFF additives taxonomy (names, classes, EFSA evaluations). */
export function loadAdditivesTaxonomy() {
  if (!additivesPromise) {
    const url = import.meta.env.VITE_OFF_ADDITIVES_URL || "https://static.openfoodfacts.org/data/taxonomies/additives.json";
    additivesPromise = fetchJson(url, { source: SRC, timeoutMs: 30000 }).catch((e) => {
      additivesPromise = null;
      throw e;
    });
  }
  return additivesPromise;
}

const en = (obj) => (obj && typeof obj === "object" ? obj.en ?? obj.xx ?? null : null);

export function describeAdditive(tag, taxonomy) {
  const code = tag.replace(/^en:/, "").toUpperCase();
  const entry = taxonomy?.[tag];
  const classes = en(entry?.additives_classes);
  return {
    tag,
    code,
    name: en(entry?.name) || code,
    classes: classes ? classes.split(",").map((c) => c.replace(/^en:/, "").replace(/-/g, " ").trim()) : [],
    description: en(entry?.description),
    efsaEvaluation: en(entry?.efsa_evaluation),
    efsaUrl: en(entry?.efsa_evaluation_url),
    efsaDate: en(entry?.efsa_evaluation_date),
    overexposureRisk: (en(entry?.efsa_evaluation_overexposure_risk) || "").replace(/^en:/, "") || null,
    vegan: (en(entry?.vegan) || "").replace(/^en:/, "") || null,
    wikidata: en(entry?.wikidata),
  };
}

/** Turns "en:gluten" → "Gluten". */
export const tagLabel = (tag) =>
  String(tag)
    .replace(/^[a-z]{2}:/, "")
    .replace(/-/g, " ")
    .replace(/^\w/, (c) => c.toUpperCase());

// ------------------------------------------------------------------ pack-size variants

const words = (s) => String(s || "").toLowerCase().replace(/\d+(\.\d+)?\s*(g|kg|ml|l)\b/g, "").split(/[^a-z0-9]+/).filter((w) => w.length > 1);

/**
 * Other pack sizes of the same product (same brand, near-identical name).
 * One search request; results are cached.
 */
export async function getSizeVariants(product, { signal } = {}) {
  if (!product?.name || !product.brand) return [];
  const { products } = await searchProducts(`${product.brand} ${product.name}`, { pageSize: 30, country: "world", signal });
  const target = new Set(words(product.name));
  const sameName = (p) => {
    const w = words(p.name);
    if (!w.length || !target.size) return false;
    const overlap = w.filter((x) => target.has(x)).length;
    return overlap / Math.max(w.length, target.size) >= 0.75;
  };
  const seen = new Map();
  for (const p of [product, ...products]) {
    if (!p.pack || (p.brand || "").toLowerCase() !== product.brand.toLowerCase() || !sameName(p)) continue;
    const key = `${p.pack.value}${p.pack.unit}`;
    if (!seen.has(key) || p.code === product.code) seen.set(key, p);
  }
  return [...seen.values()].sort((a, b) => a.pack.value - b.pack.value);
}

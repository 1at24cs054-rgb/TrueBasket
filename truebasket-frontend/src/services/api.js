/**
 * Optional Gemma 4 label-reading backend (FastAPI).
 * Used by the Scan page when a photo has no readable barcode.
 * Disabled unless VITE_API_URL is set.
 *
 * Talks to the FastAPI backend. All AI inference (Gemma 4), label extraction,
 * web research and scoring happen on the backend — this module only sends the
 * user's image + preferences and returns the backend's JSON unchanged.
 *
 * Contract: POST {VITE_API_URL}/api/products/analyze-image  (multipart/form-data)
 *   image                 File (JPEG / PNG / WebP)
 *   budget_inr            string, e.g. "450" (empty string when not set)
 *   priority              "best_value" | "ingredient_profile" | "nutrition" | "lowest_price"
 *   pack_size_preference  "any" | "small" | "medium" | "large"
 *   avoid_ingredients     JSON-encoded string array, e.g. '["palm oil"]'
 */

const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

/** True when a Gemma 4 label-reading backend is configured. */
export const labelReaderEnabled = Boolean(API_BASE);
const DEFAULT_TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS) || 90_000;

export const ANALYZE_ENDPOINT = `${API_BASE}/api/products/analyze-image`;

/** Error type carrying enough context for a helpful UI message. */
export class ApiError extends Error {
  constructor(message, { kind = "unknown", status = null, details = null } = {}) {
    super(message);
    this.name = "ApiError";
    /** "network" | "timeout" | "http" | "parse" | "cancelled" | "unknown" */
    this.kind = kind;
    this.status = status;
    this.details = details;
  }
}

/** Extracts a readable message from FastAPI-style error bodies. */
function messageFromBody(body, fallback) {
  if (!body) return fallback;
  if (typeof body === "string") return body.slice(0, 300) || fallback;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) {
    // FastAPI validation errors: [{ loc, msg, type }]
    return body.detail
      .map((d) => [d.loc?.slice(1).join("."), d.msg].filter(Boolean).join(": "))
      .join("; ");
  }
  if (typeof body.message === "string") return body.message;
  return fallback;
}

async function readBody(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/**
 * Sends a product image for analysis.
 * @param {object} params
 * @param {File} params.image
 * @param {number|string|null} params.budget
 * @param {string} params.priority
 * @param {string} params.packSizePreference
 * @param {string[]} [params.avoidIngredients]
 * @param {AbortSignal} [params.signal]   optional external cancel signal
 * @param {number} [params.timeoutMs]
 */
export async function analyzeProduct({
  image,
  budget = null,
  priority = "best_value",
  packSizePreference = "any",
  avoidIngredients = [],
  signal,
  timeoutMs = DEFAULT_TIMEOUT_MS,
}) {
  if (!API_BASE) {
    throw new ApiError("Label reading isn’t configured (VITE_API_URL is not set).", { kind: "unknown" });
  }
  if (!(image instanceof Blob)) {
    throw new ApiError("Please choose a product image first.", { kind: "unknown" });
  }

  const formData = new FormData();
  formData.append("image", image, image.name || "product.jpg");
  formData.append("budget_inr", budget === null || budget === undefined ? "" : String(budget));
  formData.append("priority", priority);
  formData.append("pack_size_preference", packSizePreference);
  formData.append("avoid_ingredients", JSON.stringify(avoidIngredients));

  // Combine the caller's signal with our own timeout.
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onExternalAbort = () => controller.abort();
  signal?.addEventListener("abort", onExternalAbort, { once: true });

  let response;
  try {
    // Do NOT set Content-Type: the browser adds the multipart boundary itself.
    response = await fetch(ANALYZE_ENDPOINT, {
      method: "POST",
      body: formData,
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
  } catch (err) {
    if (err?.name === "AbortError") {
      if (timedOut) {
        throw new ApiError(
          `The analysis took longer than ${Math.round(timeoutMs / 1000)} seconds and was stopped.`,
          { kind: "timeout" }
        );
      }
      throw new ApiError("The analysis was cancelled.", { kind: "cancelled" });
    }
    throw new ApiError(
      `Could not reach the TrueBasket backend at ${API_BASE}. Check that the FastAPI server is running and CORS allows this origin.`,
      { kind: "network", details: String(err?.message || err) }
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onExternalAbort);
  }

  const body = await readBody(response);

  if (!response.ok) {
    throw new ApiError(
      messageFromBody(body, `Product analysis failed (HTTP ${response.status}).`),
      { kind: "http", status: response.status, details: body }
    );
  }

  if (!body || typeof body !== "object") {
    throw new ApiError("The backend returned a response that is not valid JSON.", {
      kind: "parse",
      details: body,
    });
  }

  return body;
}


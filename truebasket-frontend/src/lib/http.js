/** Small fetch wrapper: timeout, cancellation, safe JSON, typed errors, in-memory cache. */

export class HttpError extends Error {
  constructor(message, { kind = "unknown", status = null, source = null } = {}) {
    super(message);
    this.name = "HttpError";
    /** "network" | "timeout" | "http" | "rate_limit" | "not_found" | "parse" | "cancelled" */
    this.kind = kind;
    this.status = status;
    this.source = source;
  }
}

const cache = new Map();
const CACHE_MS = 10 * 60 * 1000;

export async function fetchJson(url, { signal, timeoutMs = 20000, source = "server", cacheKey = url, useCache = true, init } = {}) {
  if (useCache && cacheKey) {
    const hit = cache.get(cacheKey);
    if (hit && Date.now() - hit.at < CACHE_MS) return hit.data;
  }

  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onAbort = () => controller.abort();
  signal?.addEventListener("abort", onAbort, { once: true });

  let res;
  try {
    res = await fetch(url, { ...init, signal: controller.signal, headers: { Accept: "application/json", ...(init?.headers || {}) } });
  } catch (err) {
    if (err?.name === "AbortError") {
      if (timedOut) throw new HttpError(`${source} took too long to respond.`, { kind: "timeout", source });
      throw new HttpError("Request cancelled.", { kind: "cancelled", source });
    }
    throw new HttpError(`Couldn’t reach ${source}. Please check your connection or try again.`, { kind: "network", source });
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", onAbort);
  }

  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!res.ok) {
    if (res.status === 429 || res.status === 503) {
      throw new HttpError(`${source} is limiting requests right now. Wait a minute and try again.`, { kind: "rate_limit", status: res.status, source });
    }
    if (res.status === 404) throw new HttpError("Not found.", { kind: "not_found", status: 404, source });
    const detail = typeof data?.detail === "string" ? data.detail : null;
    throw new HttpError(detail || `${source} returned an error (HTTP ${res.status}).`, { kind: "http", status: res.status, source });
  }
  if (data === null) throw new HttpError(`${source} sent a response that couldn’t be read.`, { kind: "parse", source });

  if (useCache && cacheKey) cache.set(cacheKey, { at: Date.now(), data });
  return data;
}

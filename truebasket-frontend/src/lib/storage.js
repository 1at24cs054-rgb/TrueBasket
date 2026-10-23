/** localStorage helpers that never throw (private mode, blocked storage). */
import { useCallback, useEffect, useState } from "react";

function read(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : JSON.parse(v);
  } catch {
    return fallback;
  }
}
function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* ignore */
  }
}

/** useState backed by localStorage and synced across components/tabs. */
export function useStored(key, initial) {
  const [value, setValue] = useState(() => read(key, initial));
  useEffect(() => {
    const onChange = (e) => {
      if (e.key === key || e.detail === key) setValue(read(key, initial));
    };
    window.addEventListener("storage", onChange);
    window.addEventListener("tb-storage", onChange);
    return () => {
      window.removeEventListener("storage", onChange);
      window.removeEventListener("tb-storage", onChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const set = useCallback(
    (next) => {
      setValue((prev) => {
        const v = typeof next === "function" ? next(prev) : next;
        write(key, v);
        window.dispatchEvent(new CustomEvent("tb-storage", { detail: key }));
        return v;
      });
    },
    [key]
  );
  return [value, set];
}

export const DEFAULT_PREFS = { country: "india", avoid: [], pincode: "" };
export const usePrefs = () => useStored("tb:prefs", DEFAULT_PREFS);

const RECENT_KEY = "tb:recent";
export const useRecent = () => useStored(RECENT_KEY, []);
export function pushRecent(product) {
  if (!product?.code) return;
  const item = { code: product.code, name: product.name, brand: product.brand, thumb: product.thumb, quantity: product.quantity };
  const list = [item, ...read(RECENT_KEY, []).filter((p) => p.code !== product.code)].slice(0, 8);
  write(RECENT_KEY, list);
  window.dispatchEvent(new CustomEvent("tb-storage", { detail: RECENT_KEY }));
}

/** Prices the user typed in, per product barcode. */
export const useMyPrices = (code) => useStored(`tb:prices:${code}`, {});

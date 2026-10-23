/** Minimal hash router: #/path?query — shareable links, no server config needed. */
import { useEffect, useState } from "react";

function parse() {
  const raw = window.location.hash.replace(/^#/, "") || "/";
  const [path, qs = ""] = raw.split("?");
  return { path: path || "/", params: Object.fromEntries(new URLSearchParams(qs)) };
}

export function useRoute() {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const on = () => {
      setRoute(parse());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export function href(path, params) {
  const qs = params ? new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")).toString() : "";
  return `#${path}${qs ? `?${qs}` : ""}`;
}

export function navigate(path, params) {
  window.location.hash = href(path, params);
}

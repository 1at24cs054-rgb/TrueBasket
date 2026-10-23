import { useId, useState } from "react";
import { Search } from "lucide-react";
import { isBarcode } from "../services/openFoodFacts.js";
import { navigate } from "../lib/router.js";

/** Search by product name, brand or barcode. Submits on Enter — never on every keystroke (API rate limits). */
export default function SearchBar({ initial = "", size = "lg", autoFocus = false }) {
  const [q, setQ] = useState(initial);
  const big = size === "lg";
  const id = useId();

  const submit = (e) => {
    e.preventDefault();
    const term = q.trim();
    if (!term) return;
    if (isBarcode(term)) navigate(`/product/${term.replace(/\s/g, "")}`);
    else navigate("/search", { q: term });
  };

  return (
    <form onSubmit={submit} role="search" className={`flex w-full items-center gap-2 rounded-2xl border border-cream-300 bg-white shadow-card focus-within:border-teal-500 focus-within:ring-2 focus-within:ring-teal-100 ${big ? "p-2" : "p-1"}`}>
      <Search className={`ml-2 shrink-0 text-ink-400 ${big ? "size-5" : "size-4"}`} aria-hidden="true" />
      <label htmlFor={id} className="sr-only">Search products</label>
      <input
        id={id}
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        autoFocus={autoFocus}
        placeholder={big ? "Search any packaged food — e.g. Kellogg’s muesli, Maggi, or a barcode" : "Search products, brands or a barcode…"}
        className={`min-w-0 flex-1 bg-transparent text-ink-900 placeholder:text-ink-400 focus:outline-none ${big ? "py-2 text-base" : "py-1.5 text-sm"}`}
        enterKeyHint="search"
      />
      <button type="submit" className={big ? "btn-primary px-5 py-3" : "btn-primary px-3 py-1.5"} disabled={!q.trim()}>
        Search
      </button>
    </form>
  );
}

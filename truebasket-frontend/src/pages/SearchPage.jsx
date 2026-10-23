import { useEffect, useMemo, useState } from "react";
import { Globe, Loader2, SearchX, ShoppingBasket, SlidersHorizontal, X } from "lucide-react";
import SearchBar from "../components/SearchBar.jsx";
import { EmptyState, ErrorBox, NutriScore, ProductThumb, Skeleton } from "../components/ui.jsx";
import { COUNTRIES, searchProducts } from "../services/openFoodFacts.js";
import { usePrefs } from "../lib/storage.js";
import { href } from "../lib/router.js";
import { formatPack } from "../lib/format.js";
import { SIZE_BUCKETS } from "../lib/prices.js";

const GRADE = { a: 1, b: 2, c: 3, d: 4, e: 5 };
const SORTS = [
  { id: "popular", label: "Most popular", fn: null },
  { id: "nutri", label: "Nutri-Score (best first)", fn: (a, b) => (GRADE[a.nutriscore] ?? 9) - (GRADE[b.nutriscore] ?? 9) },
  { id: "small", label: "Pack size: small to large", fn: (a, b) => (a.pack?.value ?? 1e9) - (b.pack?.value ?? 1e9) },
  { id: "large", label: "Pack size: large to small", fn: (a, b) => (b.pack?.value ?? -1) - (a.pack?.value ?? -1) },
];

function Card({ p }) {
  return (
    <li className="min-w-0">
      <div className="card group flex h-full flex-col p-3 transition-shadow hover:shadow-lift">
        <a href={href(`/product/${p.code}`)} className="relative block">
          <ProductThumb src={p.thumb} alt={p.name} size="card" />
          {p.quantity && <span className="absolute left-2 top-2 rounded-lg bg-teal-800/90 px-2 py-0.5 text-xs font-bold text-cream-50">{formatPack(p.pack) || p.quantity}</span>}
        </a>
        <div className="mt-3 flex min-w-0 flex-1 flex-col px-1">
          <p className="truncate text-xs font-semibold uppercase tracking-wider text-ink-400">{p.brand || "Brand unknown"}</p>
          <a href={href(`/product/${p.code}`)} className="mt-0.5 line-clamp-2 font-semibold leading-snug text-ink-900 hover:text-teal-700">{p.name}</a>
          <p className="mt-0.5 text-sm text-ink-500">{p.quantity || "Size not listed"}</p>
          <div className="mt-auto space-y-2 pt-3">
            <NutriScore grade={p.nutriscore} size="sm" />
            <a href={href(`/product/${p.code}`, { tab: "buy" })} className="btn-secondary w-full px-3 py-2 text-[13px]"><ShoppingBasket className="size-4" aria-hidden="true" /> Compare prices</a>
          </div>
        </div>
      </div>
    </li>
  );
}

function Filters({ items, f, setF, country, setCountry }) {
  const brands = useMemo(() => {
    const counts = new Map();
    items.forEach((p) => p.brand && counts.set(p.brand, (counts.get(p.brand) || 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10);
  }, [items]);
  const toggle = (key, val) => setF((s) => ({ ...s, [key]: s[key].includes(val) ? s[key].filter((x) => x !== val) : [...s[key], val] }));
  const count = (test) => items.filter(test).length;

  return (
    <div className="space-y-5">
      <div>
        <label htmlFor="country-filter" className="mb-1.5 flex items-center gap-2 text-sm font-bold"><Globe className="size-4 text-teal-600" aria-hidden="true" /> Sold in</label>
        <select id="country-filter" className="field-input py-2" value={country} onChange={(e) => setCountry(e.target.value)}>
          {COUNTRIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
        </select>
      </div>
      <fieldset>
        <legend className="text-sm font-bold">Pack size / weight</legend>
        <div className="mt-2 space-y-2">
          {SIZE_BUCKETS.map((b) => (
            <label key={b.id} className="flex items-center gap-2.5 text-sm text-ink-700">
              <input type="checkbox" className="size-4 accent-teal-700" checked={f.sizes.includes(b.id)} onChange={() => toggle("sizes", b.id)} />
              {b.label} <span className="ml-auto text-xs text-ink-400">{count((p) => p.pack && b.test(p.pack.value))}</span>
            </label>
          ))}
        </div>
      </fieldset>
      {brands.length > 0 && (
        <fieldset>
          <legend className="text-sm font-bold">Brand</legend>
          <div className="mt-2 max-h-48 space-y-2 overflow-y-auto pr-1">
            {brands.map(([b, n]) => (
              <label key={b} className="flex items-center gap-2.5 text-sm text-ink-700">
                <input type="checkbox" className="size-4 accent-teal-700" checked={f.brands.includes(b)} onChange={() => toggle("brands", b)} />
                <span className="truncate">{b}</span> <span className="ml-auto text-xs text-ink-400">{n}</span>
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <fieldset>
        <legend className="text-sm font-bold">Nutri-Score</legend>
        <div className="mt-2 flex gap-1.5">
          {["a", "b", "c", "d", "e"].map((g) => (
            <button key={g} type="button" aria-pressed={f.grades.includes(g)} onClick={() => toggle("grades", g)}
              className={`grid size-9 place-items-center rounded-lg text-sm font-bold uppercase ring-1 transition-colors ${f.grades.includes(g) ? "bg-teal-700 text-cream-50 ring-teal-700" : "bg-white text-ink-700 ring-cream-300 hover:ring-teal-200"}`}>{g}</button>
          ))}
        </div>
      </fieldset>
      <label className="flex items-center gap-2.5 text-sm text-ink-700">
        <input type="checkbox" className="size-4 accent-teal-700" checked={f.noPalm} onChange={(e) => setF((s) => ({ ...s, noPalm: e.target.checked }))} /> No palm oil
      </label>
    </div>
  );
}

const EMPTY = { sizes: [], brands: [], grades: [], noPalm: false };

export default function SearchPage({ query }) {
  const [prefs, setPrefs] = usePrefs();
  const country = prefs.country;
  const [state, setState] = useState({ items: [], count: 0, page: 0, hasMore: false, loading: true, error: null });
  const [nonce, setNonce] = useState(0);
  const [f, setF] = useState(EMPTY);
  const [sort, setSort] = useState("popular");
  const [showFilters, setShowFilters] = useState(false);

  useEffect(() => {
    if (!query) return undefined;
    const controller = new AbortController();
    setState({ items: [], count: 0, page: 0, hasMore: false, loading: true, error: null });
    setF(EMPTY);
    searchProducts(query, { page: 1, country, signal: controller.signal }).then(
      (r) => setState({ items: r.products, count: r.count, page: 1, hasMore: r.hasMore, loading: false, error: null }),
      (e) => e.kind !== "cancelled" && setState((s) => ({ ...s, loading: false, error: e }))
    );
    return () => controller.abort();
  }, [query, country, nonce]);

  const loadMore = () => {
    setState((s) => ({ ...s, loading: true }));
    searchProducts(query, { page: state.page + 1, country }).then(
      (r) => setState((s) => ({ ...s, items: [...s.items, ...r.products.filter((p) => !s.items.some((x) => x.code === p.code))], page: r.page, hasMore: r.hasMore, loading: false })),
      (e) => setState((s) => ({ ...s, loading: false, error: e }))
    );
  };

  const shown = useMemo(() => {
    let list = state.items.filter((p) => {
      if (f.sizes.length && !(p.pack && SIZE_BUCKETS.some((b) => f.sizes.includes(b.id) && b.test(p.pack.value)))) return false;
      if (f.brands.length && !f.brands.includes(p.brand)) return false;
      if (f.grades.length && !f.grades.includes(p.nutriscore)) return false;
      if (f.noPalm && p.analysis.includes("en:palm-oil")) return false;
      return true;
    });
    const s = SORTS.find((x) => x.id === sort);
    return s.fn ? [...list].sort(s.fn) : list;
  }, [state.items, f, sort]);
  const activeCount = f.sizes.length + f.brands.length + f.grades.length + (f.noPalm ? 1 : 0);
  const setCountry = (c) => setPrefs((p) => ({ ...p, country: c }));
  const countryLabel = COUNTRIES.find((c) => c.id === country)?.label ?? "Worldwide";

  return (
    <div>
      <div className="mb-6 md:hidden"><SearchBar initial={query} size="sm" key={query} /></div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow mb-1">Search results</p>
          <h1 className="font-display text-3xl font-semibold tracking-tight">“{query}”</h1>
          {!state.loading && !state.error && <p className="mt-1 text-sm text-ink-500">{state.count.toLocaleString("en-IN")} products · {countryLabel}{activeCount ? ` · showing ${shown.length} of ${state.items.length} loaded` : ""}</p>}
        </div>
        <div className="flex items-center gap-2">
          <button type="button" className="btn-secondary lg:hidden" onClick={() => setShowFilters((s) => !s)} aria-expanded={showFilters}>
            <SlidersHorizontal className="size-4" aria-hidden="true" /> Filters{activeCount ? ` (${activeCount})` : ""}
          </button>
          <label className="flex items-center gap-2 text-sm font-semibold text-ink-700"><span className="hidden sm:inline">Sort</span>
            <select className="field-input w-auto py-2" value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort results">
              {SORTS.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </label>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[230px_minmax(0,1fr)]">
        <aside className={`${showFilters ? "block" : "hidden"} h-max rounded-[var(--radius-card)] border border-cream-200 bg-white p-4 shadow-card lg:sticky lg:top-24 lg:block`} aria-label="Filters">
          <div className="mb-4 flex items-center justify-between">
            <p className="font-semibold">Filters</p>
            {activeCount > 0 && <button type="button" className="inline-flex items-center gap-1 text-xs font-semibold text-teal-700 underline" onClick={() => setF(EMPTY)}><X className="size-3" aria-hidden="true" />Clear</button>}
          </div>
          <Filters items={state.items} f={f} setF={setF} country={country} setCountry={setCountry} />
          <p className="mt-4 text-xs text-ink-400">Filters apply to the results loaded so far.</p>
        </aside>

        <div className="min-w-0">
          {state.error && state.items.length === 0 ? (
            <ErrorBox error={state.error} title="Search failed" onRetry={() => setNonce((n) => n + 1)} />
          ) : state.loading && state.items.length === 0 ? (
            <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4" aria-label="Loading results">
              {Array.from({ length: 8 }, (_, i) => <li key={i}><Skeleton className="aspect-[3/4] w-full" /></li>)}
            </ul>
          ) : state.items.length === 0 ? (
            <EmptyState icon={SearchX} title="No products found"
              action={country !== "world" && <button type="button" className="btn-secondary" onClick={() => setCountry("world")}>Search worldwide instead</button>}>
              Try a shorter name, the brand alone, or the barcode number.{country !== "world" && ` You’re only seeing products recorded as sold in ${countryLabel}.`}
            </EmptyState>
          ) : (
            <>
              {shown.length === 0 ? (
                <EmptyState icon={SlidersHorizontal} title="No products match these filters" action={<button type="button" className="btn-secondary" onClick={() => setF(EMPTY)}>Clear filters</button>}>
                  {state.hasMore ? "Load more results or loosen the filters." : "Try loosening the filters."}
                </EmptyState>
              ) : (
                <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-4" data-testid="results">
                  {shown.map((p) => <Card key={p.code} p={p} />)}
                </ul>
              )}
              {state.error && <div className="mt-6"><ErrorBox error={state.error} title="Couldn’t load more" /></div>}
              {state.hasMore && (
                <div className="mt-8 text-center">
                  <button type="button" className="btn-secondary" onClick={loadMore} disabled={state.loading}>
                    {state.loading && <Loader2 className="size-4 animate-spin" aria-hidden="true" />} Load more results
                  </button>
                </div>
              )}
            </>
          )}
          <p className="mt-10 text-center text-xs text-ink-400">Results from Open Food Facts, a community database. Can’t find a product? It may not have been added yet.</p>
        </div>
      </div>
    </div>
  );
}

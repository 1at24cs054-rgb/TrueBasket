import { useEffect } from "react";
import { ArrowLeft, Ban, BadgeCheck, Database, ExternalLink, Leaf, PackageSearch, Scale, Store } from "lucide-react";
import IngredientsPanel from "../components/IngredientsPanel.jsx";
import AdditivesPanel from "../components/AdditivesPanel.jsx";
import NutritionPanel from "../components/NutritionPanel.jsx";
import AlternativesPanel from "../components/AlternativesPanel.jsx";
import WhereToBuy from "../components/WhereToBuy.jsx";
import SizeVariants from "../components/SizeVariants.jsx";
import { Badge, EmptyState, ErrorBox, Notice, NutriScore, Nova, Skeleton } from "../components/ui.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { getProduct, tagLabel } from "../services/openFoodFacts.js";
import { matchAvoid } from "../lib/avoid.js";
import { pushRecent, usePrefs } from "../lib/storage.js";
import { formatDate } from "../lib/format.js";
import { href } from "../lib/router.js";

const TABS = [
  { id: "overview", label: "Ingredients & nutrition", short: "Ingredients", icon: Leaf },
  { id: "alternatives", label: "Compare alternatives", short: "Compare", icon: Scale },
  { id: "buy", label: "Where to buy", short: "Buy", icon: Store },
];

const ANALYSIS = {
  "en:palm-oil": { tone: "amber", label: "Contains palm oil" },
  "en:palm-oil-free": { tone: "sage", label: "Palm-oil free" },
  "en:vegan": { tone: "sage", label: "Vegan" },
  "en:non-vegan": { tone: "slate", label: "Not vegan" },
  "en:vegetarian": { tone: "sage", label: "Vegetarian" },
  "en:non-vegetarian": { tone: "clay", label: "Not vegetarian" },
};

function Ring({ value }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  const r = 34;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 84 84" className="size-24 shrink-0" role="img" aria-label={`Data completeness ${pct}%`}>
      <circle cx="42" cy="42" r={r} fill="none" stroke="#e3ede9" strokeWidth="8" />
      <circle cx="42" cy="42" r={r} fill="none" stroke="#1b655d" strokeWidth="8" strokeLinecap="round" strokeDasharray={`${(pct / 100) * c} ${c}`} transform="rotate(-90 42 42)" />
      <text x="42" y="48" textAnchor="middle" fontFamily="Fraunces, Georgia, serif" fontSize="19" fontWeight="600" fill="#0b3b37">{pct}%</text>
    </svg>
  );
}

function MatchCard({ product, via }) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-4">
        {typeof product.completeness === "number" ? <Ring value={product.completeness} /> : null}
        <div>
          <p className="font-display text-xl font-semibold">{via ? "Barcode matched" : "Product record"}</p>
          <p className="mt-1 text-sm text-ink-500">
            {typeof product.completeness === "number" ? "How complete this product’s data is on Open Food Facts." : "Data from Open Food Facts."}
          </p>
        </div>
      </div>
      <div className="mt-4 flex items-start gap-3 rounded-2xl bg-sage-50 p-4">
        <BadgeCheck className="mt-0.5 size-6 shrink-0 text-teal-700" aria-hidden="true" />
        <div className="text-sm">
          <p className="font-semibold text-teal-900">{via === "photo" ? "Read from your photo" : via === "camera" ? "Scanned with your camera" : "Exact barcode lookup"}</p>
          <p className="text-ink-700">Barcode {product.code} found in Open Food Facts{product.lastModified ? `, updated ${formatDate(product.lastModified)}` : ""}.</p>
        </div>
      </div>
      {product.sourceUrl && (
        <a href={product.sourceUrl} target="_blank" rel="noopener noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-teal-700 hover:underline">
          View or fix this product on Open Food Facts <ExternalLink className="size-3" aria-hidden="true" />
        </a>
      )}
    </div>
  );
}

function Header({ product, avoidHits }) {
  const tags = product.analysis.filter((t) => ANALYSIS[t]);
  return (
    <section aria-labelledby="product-title">
      <div className="flex flex-col gap-6 sm:flex-row">
        <div className="shrink-0">
          {product.image ? (
            <img src={product.image} alt={product.name || "Product"} className="h-64 w-full rounded-3xl border border-cream-200 bg-white object-contain p-2 shadow-card sm:h-64 sm:w-56" />
          ) : (
            <div className="grid h-56 w-full place-items-center rounded-3xl bg-cream-200/60 text-ink-400 sm:w-56"><PackageSearch className="size-10" aria-hidden="true" /></div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <Badge tone="sage" icon={BadgeCheck}>Identified product</Badge>
          <h1 id="product-title" className="mt-3 font-display text-3xl font-semibold leading-tight tracking-tight sm:text-[2.6rem]">{product.name || "Unnamed product"}</h1>
          {product.description && <p className="mt-1 text-lg text-ink-700">{product.description}</p>}
          <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[15px] text-ink-500">
            {product.quantity && <span>{product.quantity}</span>}
            {product.brands && <><span className="text-cream-300">|</span><span>{product.brands}</span></>}
            <span className="text-cream-300">|</span><span className="inline-flex items-center gap-1"><Database className="size-3.5" aria-hidden="true" /> {product.code}</span>
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {product.categoryLabel && <Badge tone="slate">{product.categoryLabel}</Badge>}
            {tags.map((t) => <Badge key={t} tone={ANALYSIS[t].tone}>{ANALYSIS[t].label}</Badge>)}
            {product.labels.slice(0, 3).map((l) => <Badge key={l} tone="teal">{tagLabel(l)}</Badge>)}
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <NutriScore grade={product.nutriscore} />
            <Nova group={product.nova} />
          </div>
          <div className="mt-4"><SizeVariants product={product} /></div>
        </div>
      </div>
      {avoidHits.length > 0 && (
        <div className="mt-5">
          <Notice tone="clay" icon={Ban} title="Contains items on your avoid list">
            {avoidHits.map((h) => `${h.term} (${h.hits.slice(0, 3).join(", ")})`).join(" · ")}
          </Notice>
        </div>
      )}
    </section>
  );
}

export default function ProductPage({ code, tab = "overview", via, onOpenPrefs }) {
  const [prefs] = usePrefs();
  const { data: product, loading, error, retry } = useAsync((signal) => getProduct(code, { signal }), [code]);

  useEffect(() => {
    if (product) pushRecent(product);
  }, [product]);

  if (loading) {
    return (
      <div className="space-y-6" aria-busy="true">
        <div className="flex gap-6"><Skeleton className="h-64 w-56" /><div className="flex-1 space-y-3"><Skeleton className="h-6 w-40" /><Skeleton className="h-10 w-3/4" /><Skeleton className="h-5 w-1/2" /></div></div>
        <div className="grid gap-6 lg:grid-cols-12"><Skeleton className="h-96 lg:col-span-8" /><Skeleton className="h-96 lg:col-span-4" /></div>
      </div>
    );
  }
  if (error?.kind === "not_found") {
    return (
      <EmptyState icon={PackageSearch} title="Product not found" action={<a className="btn-primary" href={href("/")}>Search by name instead</a>}>
        {error.message} You can add it on{" "}
        <a className="font-semibold text-teal-700 hover:underline" href="https://world.openfoodfacts.org/contribute" target="_blank" rel="noopener noreferrer">Open Food Facts</a>, and it will appear here.
      </EmptyState>
    );
  }
  if (error) return <ErrorBox error={error} title="Couldn’t load this product" onRetry={retry} />;
  if (!product) return null;

  const active = TABS.some((t) => t.id === tab) ? tab : "overview";
  const avoidHits = matchAvoid(product, prefs.avoid);

  return (
    <div className="space-y-6">
      <button type="button" onClick={() => history.back()} className="inline-flex items-center gap-2 text-sm font-semibold text-ink-700 hover:text-teal-700">
        <ArrowLeft className="size-4" aria-hidden="true" /> Back
      </button>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Header product={product} avoidHits={avoidHits} />
        <MatchCard product={product} via={via} />
      </div>

      <nav aria-label="Product sections" className="sticky top-16 z-20 -mx-4 bg-cream-100/95 px-4 py-2 backdrop-blur-sm sm:mx-0 sm:px-0">
        <ul className="flex rounded-2xl border border-cream-200 bg-white p-1 shadow-card">
          {TABS.map(({ id, label, short, icon: Icon }) => (
            <li key={id} className="min-w-0 flex-1">
              <a href={href(`/product/${code}`, id === "overview" ? null : { tab: id })} aria-current={active === id ? "page" : undefined}
                className={`flex items-center justify-center gap-2 rounded-xl px-2 py-2.5 text-sm font-semibold transition-colors ${active === id ? "bg-teal-700 text-cream-50" : "text-ink-700 hover:bg-cream-100"}`}>
                <Icon className="hidden size-4 min-[400px]:block" aria-hidden="true" />
                <span className="sm:hidden">{short}</span><span className="hidden sm:inline">{label}</span>
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {active === "overview" && (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="min-w-0"><IngredientsPanel product={product} avoid={prefs.avoid} /></div>
          <div className="min-w-0 space-y-6">
            <NutritionPanel product={product} />
            <AdditivesPanel additives={product.additives} />
          </div>
        </div>
      )}
      {active === "alternatives" && <AlternativesPanel product={product} country={prefs.country} avoid={prefs.avoid} />}
      {active === "buy" && <WhereToBuy product={product} prefs={prefs} onOpenPrefs={onOpenPrefs} />}
    </div>
  );
}

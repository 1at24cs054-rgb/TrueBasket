import { ArrowRight, BadgeIndianRupee, Check, Database, HeartPulse, Leaf, Scale, ShieldCheck } from "lucide-react";
import UploadCard from "../components/UploadCard.jsx";
import { ProductThumb } from "../components/ui.jsx";
import { BasketIllustration, LeafSprig, Script } from "../components/art.jsx";
import { CATEGORIES } from "../config/categories.js";
import { href } from "../lib/router.js";
import { useRecent } from "../lib/storage.js";

const FEATURES = [
  { icon: Scale, title: "Compare products", sub: "Same category, clear criteria", tint: "bg-teal-50 text-teal-700" },
  { icon: HeartPulse, title: "Nutrition insights", sub: "Sugar, fibre, salt, fat", tint: "bg-clay-50 text-clay-700" },
  { icon: BadgeIndianRupee, title: "Find better deals", sub: "Cheapest store per 100 g", tint: "bg-amber-50 text-amber-600" },
  { icon: Leaf, title: "Ingredient check", sub: "Additives & your avoid list", tint: "bg-sage-50 text-sage-700" },
];

export default function HomePage() {
  const [recent] = useRecent();

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
      <div className="min-w-0 space-y-6">
        {/* Hero */}
        <section className="relative overflow-hidden rounded-[28px] bg-[#efe3c9] px-6 py-8 sm:px-10 sm:py-10">
          <div className="relative z-10 max-w-md">
            <h1 className="font-display text-4xl font-semibold leading-[1.05] tracking-tight text-teal-900 sm:text-5xl">Smarter groceries.<br />A healthier you.</h1>
            <p className="mt-4 text-[15px] text-ink-700">Scan any packaged food to see what’s really inside, compare better options and find the store where it’s cheapest.</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <a href={href("/scan")} className="btn-primary px-5 py-3">Upload a product <ArrowRight className="size-4" aria-hidden="true" /></a>
              <a href={href("/categories")} className="btn-secondary px-5 py-3">Browse categories</a>
            </div>
          </div>
          <BasketIllustration className="pointer-events-none absolute -bottom-4 right-0 hidden w-[52%] max-w-[440px] sm:block" />
          <Script className="absolute right-6 top-6 hidden rotate-[-6deg] text-right text-2xl text-teal-800 md:block">Same groceries,<br />a brighter tomorrow</Script>
        </section>

        {/* Feature tiles */}
        <ul className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {FEATURES.map(({ icon: Icon, title, sub, tint }) => (
            <li key={title} className="card flex items-center gap-3 p-4">
              <span className={`grid size-11 shrink-0 place-items-center rounded-2xl ${tint}`}><Icon className="size-5" aria-hidden="true" /></span>
              <span className="min-w-0"><span className="block text-sm font-bold leading-tight">{title}</span><span className="block text-xs text-ink-500">{sub}</span></span>
            </li>
          ))}
        </ul>

        {/* Upload */}
        <section className="card p-5 sm:p-7" aria-labelledby="upload-heading">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-2">
            <div>
              <h2 id="upload-heading" className="font-display text-2xl font-semibold tracking-tight">Upload a product image</h2>
              <p className="mt-1 text-sm text-ink-500">Snap the barcode, pick a photo from your gallery or files, or scan live with your camera.</p>
            </div>
          </div>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
            <UploadCard />
            <div className="rounded-2xl bg-cream-50 p-5">
              <p className="text-sm font-bold">What you’ll see</p>
              <ul className="mt-3 space-y-2.5 text-sm text-ink-700">
                {["Every ingredient, with what’s declared on the pack", "Additives with EFSA evaluations", "Nutri-Score, NOVA and nutrition per 100 g", "Better options in the same category", "Where it’s cheapest — Blinkit, Instamart, Zepto, DMart, JioMart and more"].map((t) => (
                  <li key={t} className="flex gap-2.5"><span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-teal-700 text-cream-50"><Check className="size-3" aria-hidden="true" /></span>{t}</li>
                ))}
              </ul>
              <p className="mt-4 text-xs text-ink-500">Tip: the barcode is usually on the back or bottom of the pack.</p>
            </div>
          </div>
        </section>

        {/* Categories */}
        <section aria-labelledby="cat-heading">
          <div className="mb-3 flex items-center justify-between">
            <h2 id="cat-heading" className="font-display text-2xl font-semibold tracking-tight">Popular categories</h2>
            <a href={href("/categories")} className="inline-flex items-center gap-1 text-sm font-semibold text-teal-700 hover:underline">View all <ArrowRight className="size-4" aria-hidden="true" /></a>
          </div>
          <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {CATEGORIES.slice(0, 6).map(({ q, label, sub, icon: Icon, tint, ink }) => (
              <li key={q}>
                <a href={href("/search", { q })} className="card group flex h-full flex-col overflow-hidden transition-shadow hover:shadow-lift">
                  <span className="grid h-24 place-items-center" style={{ background: tint, color: ink }}><Icon className="size-10 transition-transform group-hover:scale-110" aria-hidden="true" /></span>
                  <span className="p-3"><span className="block text-sm font-bold">{label}</span><span className="block text-xs text-ink-500">{sub}</span></span>
                </a>
              </li>
            ))}
          </ul>
        </section>

        {recent.length > 0 && (
          <section aria-labelledby="recent-heading">
            <h2 id="recent-heading" className="mb-3 font-display text-2xl font-semibold tracking-tight">Recently viewed</h2>
            <ul className="flex gap-3 overflow-x-auto pb-2">
              {recent.map((p) => (
                <li key={p.code} className="w-64 shrink-0">
                  <a href={href(`/product/${p.code}`)} className="card flex items-center gap-3 p-3 hover:shadow-lift">
                    <ProductThumb src={p.thumb} alt={p.name || p.code} size="sm" />
                    <span className="min-w-0"><span className="block truncate text-sm font-semibold">{p.name || p.code}</span><span className="block truncate text-xs text-ink-500">{[p.brand, p.quantity].filter(Boolean).join(" · ")}</span></span>
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {/* Right rail */}
      <aside className="space-y-4">
        <div className="relative overflow-hidden rounded-[var(--radius-card)] bg-[#ece2cc] p-6">
          <LeafSprig className="absolute -right-4 bottom-0 h-32" />
          <h2 className="font-display text-2xl font-semibold leading-tight text-teal-900">Your smarter<br />basket awaits</h2>
          <ul className="mt-4 space-y-2.5 text-sm font-medium text-ink-700">
            {["Healthier choices", "Better savings", "Honest insights", "No paid rankings"].map((t) => (
              <li key={t} className="flex items-center gap-2.5"><span className="grid size-5 place-items-center rounded-full bg-teal-700 text-cream-50"><Check className="size-3" aria-hidden="true" /></span>{t}</li>
            ))}
          </ul>
        </div>
        <div className="relative overflow-hidden rounded-[var(--radius-card)] bg-teal-800 p-6 text-cream-50">
          <LeafSprig className="absolute -bottom-4 -right-4 h-36 opacity-90" tone="dark" />
          <Script className="relative text-[2rem]">“Choose better today for a brighter tomorrow.”</Script>
        </div>
        <div className="card p-5">
          <h2 className="text-sm font-bold">Our promise</h2>
          <ul className="mt-3 space-y-3 text-sm text-ink-700">
            <li className="flex gap-2.5"><ShieldCheck className="size-4 shrink-0 text-teal-700" aria-hidden="true" />Nothing is guessed. Missing data stays missing.</li>
            <li className="flex gap-2.5"><Database className="size-4 shrink-0 text-teal-700" aria-hidden="true" />Live, open data from Open Food Facts.</li>
            <li className="flex gap-2.5"><Scale className="size-4 shrink-0 text-teal-700" aria-hidden="true" />Every pick shows its criteria.</li>
          </ul>
        </div>
      </aside>
    </div>
  );
}

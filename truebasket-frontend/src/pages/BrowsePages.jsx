import { Clock, Trash2 } from "lucide-react";
import { EmptyState, ProductThumb, SectionHeading } from "../components/ui.jsx";
import { CATEGORIES } from "../config/categories.js";
import { href } from "../lib/router.js";
import { useRecent } from "../lib/storage.js";

export function CategoriesPage() {
  return (
    <div>
      <SectionHeading eyebrow="Browse" title="Categories" description="Pick a category to see products sold in your country setting." />
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {CATEGORIES.map(({ q, label, sub, icon: Icon, tint, ink }) => (
          <li key={label}>
            <a href={href("/search", { q })} className="card group flex h-full flex-col overflow-hidden transition-shadow hover:shadow-lift">
              <span className="grid h-28 place-items-center" style={{ background: tint, color: ink }}><Icon className="size-11 transition-transform group-hover:scale-110" aria-hidden="true" /></span>
              <span className="p-3.5"><span className="block font-bold">{label}</span><span className="block text-xs text-ink-500">{sub}</span></span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RecentPage() {
  const [recent, setRecent] = useRecent();
  return (
    <div>
      <SectionHeading eyebrow="Your history" title="Recently viewed" description="Saved on this device only."
        action={recent.length > 0 && <button type="button" className="btn-ghost" onClick={() => setRecent([])}><Trash2 className="size-4" aria-hidden="true" /> Clear</button>} />
      {recent.length === 0 ? (
        <EmptyState icon={Clock} title="Nothing here yet" action={<a href={href("/scan")} className="btn-primary">Scan a product</a>}>Products you open will appear here.</EmptyState>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {recent.map((p) => (
            <li key={p.code}>
              <a href={href(`/product/${p.code}`)} className="card flex items-center gap-3 p-3 hover:shadow-lift">
                <ProductThumb src={p.thumb} alt={p.name || p.code} size="md" />
                <span className="min-w-0"><span className="block truncate font-semibold">{p.name || p.code}</span><span className="block truncate text-sm text-ink-500">{[p.brand, p.quantity].filter(Boolean).join(" · ")}</span></span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

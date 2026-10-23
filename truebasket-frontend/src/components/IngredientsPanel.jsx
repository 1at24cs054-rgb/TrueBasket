import { useState } from "react";
import { Ban, ChevronDown, Image as ImageIcon, ListChecks, ScanText } from "lucide-react";
import { Badge, EmptyState } from "./ui.jsx";
import { ingredientMatchesAvoid } from "../lib/avoid.js";
import { ingredientInfo } from "../lib/ingredientInfo.js";
import { tagLabel } from "../services/openFoodFacts.js";
import { LeafSprig } from "./art.jsx";

function Qty({ ing }) {
  if (typeof ing.percent === "number") return <Badge tone="teal">{ing.percent}% on pack</Badge>;
  if (typeof ing.percentEstimate === "number")
    return <span title="Estimated by Open Food Facts from ingredient order and nutrition — not printed on the pack"><Badge tone="slate">≈{Math.round(ing.percentEstimate)}% est.</Badge></span>;
  return <Badge tone="slate">Qty not declared</Badge>;
}

function Row({ ing, index, avoid, fromLabel }) {
  const [open, setOpen] = useState(false);
  const info = ingredientInfo(ing.text);
  const Icon = info.icon;
  const avoided = ingredientMatchesAvoid(ing.text, avoid) || ing.sub.some((s) => ingredientMatchesAvoid(s.text, avoid));
  const hasMore = ing.sub.length > 0 || ing.vegan || ing.vegetarian || ing.fromPalmOil;

  return (
    <li className={`${avoided ? "bg-clay-50/60" : ""}`}>
      <button type="button" onClick={() => hasMore && setOpen((o) => !o)} aria-expanded={hasMore ? open : undefined}
        className={`grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 text-left sm:grid-cols-[auto_minmax(0,1fr)_auto_auto_auto] sm:px-5 ${hasMore ? "cursor-pointer hover:bg-cream-50" : "cursor-default"}`}>
        <span className="grid size-11 place-items-center rounded-xl" style={{ background: info.tint, color: info.ink }}><Icon className="size-5" aria-hidden="true" /></span>
        <span className="min-w-0">
          <span className="flex flex-wrap items-center gap-2">
            <span className="font-semibold first-letter:uppercase">{ing.text}</span>
            {avoided && <Badge tone="clay" icon={Ban}>Avoid list</Badge>}
          </span>
          <span className="block text-sm text-ink-500">{info.role}{index === 0 ? " · main ingredient" : ""}</span>
        </span>
        <span className="hidden sm:block"><Qty ing={ing} /></span>
        <span className="hidden items-center gap-1.5 text-xs text-ink-500 sm:flex">
          {fromLabel && <><ImageIcon className="size-3.5" aria-hidden="true" /> Seen on pack</>}
        </span>
        <span className="flex items-center gap-2">
          {info.tag ? <Badge tone={info.tag.tone}>{info.tag.label}</Badge> : <span className="hidden w-4 sm:block" />}
          {hasMore && <ChevronDown className={`size-4 text-ink-400 transition-transform ${open ? "rotate-180" : ""}`} aria-hidden="true" />}
        </span>
      </button>
      <div className="flex flex-wrap gap-1.5 px-4 pb-3 pl-[4.75rem] sm:hidden"><Qty ing={ing} /></div>
      {open && (
        <div className="space-y-1 px-5 pb-4 pl-[4.75rem] text-sm text-ink-700 sm:pl-[5.25rem]">
          {ing.sub.length > 0 && <p><span className="font-semibold">Contains:</span> {ing.sub.map((s) => s.text).join(", ")}</p>}
          <p className="flex flex-wrap gap-1.5">
            {ing.vegan === "yes" && <Badge tone="sage">Vegan</Badge>}
            {ing.vegan === "no" && <Badge tone="slate">Not vegan</Badge>}
            {ing.vegetarian === "no" && <Badge tone="clay">Not vegetarian</Badge>}
            {ing.fromPalmOil === "yes" && <Badge tone="amber">From palm oil</Badge>}
          </p>
        </div>
      )}
    </li>
  );
}

export default function IngredientsPanel({ product, avoid }) {
  const list = product.ingredients;
  const fromLabel = Boolean(product.ingredientsText);

  return (
    <section aria-labelledby="ing-heading" className="space-y-4">
      <div className="card overflow-hidden">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-cream-200 px-5 py-4">
          <div className="flex items-start gap-3">
            <LeafSprig className="mt-0.5 h-9 w-7 shrink-0" />
            <div>
              <h2 id="ing-heading" className="font-display text-2xl font-semibold tracking-tight">Ingredient breakdown</h2>
              <p className="text-sm text-ink-500">In the order printed on the pack. Tap an ingredient for details.</p>
            </div>
          </div>
          {list.length > 0 && <span className="rounded-full bg-cream-100 px-3 py-1 text-sm font-semibold text-ink-700">{list.length} ingredients</span>}
        </div>

        {list.length === 0 ? (
          <div className="p-5">
            <EmptyState icon={ListChecks} title="No ingredient list yet">
              Nobody has added this product’s ingredients to Open Food Facts yet.{" "}
              {product.sourceUrl && <a className="font-semibold text-teal-700 hover:underline" href={product.sourceUrl} target="_blank" rel="noopener noreferrer">Add them there</a>}
            </EmptyState>
          </div>
        ) : (
          <ol className="divide-y divide-cream-200">
            {list.map((ing, i) => <Row key={`${ing.text}-${i}`} ing={ing} index={i} avoid={avoid} fromLabel={fromLabel} />)}
          </ol>
        )}

        {product.ingredientsText && (
          <details className="group border-t border-cream-200 px-5 py-3">
            <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-semibold text-teal-700">
              <ScanText className="size-4" aria-hidden="true" /> Read the full text as printed
              <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden="true" />
            </summary>
            <p className="mt-3 rounded-xl bg-cream-50 p-3 text-[13px] leading-relaxed text-ink-700">{product.ingredientsText.replace(/_/g, "")}</p>
          </details>
        )}
      </div>

      {(product.allergens.length > 0 || product.traces.length > 0) && (
        <div className="card p-5">
          <h3 className="text-sm font-bold">Allergens</h3>
          <div className="mt-2 flex flex-wrap gap-1.5">{product.allergens.map((a) => <Badge key={a} tone="clay">{tagLabel(a)}</Badge>)}</div>
          {product.traces.length > 0 && <p className="mt-3 text-sm text-ink-700"><span className="font-semibold">May contain traces of:</span> {product.traces.map(tagLabel).join(", ")}</p>}
        </div>
      )}
    </section>
  );
}

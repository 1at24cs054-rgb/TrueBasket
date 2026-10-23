import { useMemo, useState } from "react";
import { Award, BadgeIndianRupee, Candy, Check, FlaskConical, Lightbulb, SearchX, ShoppingBasket, TrendingDown, Wheat, X } from "lucide-react";
import { EmptyState, ErrorBox, NutriScore, ProductThumb, Skeleton } from "./ui.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { getAlternatives, tagLabel } from "../services/openFoodFacts.js";
import { formatINR, formatNutrient, formatPerHundred, isNum } from "../lib/format.js";
import { bestOffer, offersFor } from "../lib/prices.js";
import { getLivePrices, priceFeedEnabled } from "../services/priceFeed.js";
import { retailerQuery } from "../config/retailers.js";
import { href } from "../lib/router.js";
import { matchAvoid } from "../lib/avoid.js";

const GRADE = { a: 1, b: 2, c: 3, d: 4, e: 5 };
const v = (p, k) => p.per100?.[k];
const palm = (p) => p.analysis.includes("en:palm-oil");

/** One stated criterion per rank. A product is only ranked if it beats the scanned product on it. */
const CRITERIA = [
  {
    key: "nutri", title: "Better Nutri-Score", icon: Award, band: "bg-amber-50 text-amber-600 border-amber-600/20",
    better: (a, p) => GRADE[a.nutriscore] && (!GRADE[p.nutriscore] || GRADE[a.nutriscore] < GRADE[p.nutriscore]),
    sort: (a, b) => GRADE[a.nutriscore] - GRADE[b.nutriscore] || (v(a, "total_sugars_g") ?? 99) - (v(b, "total_sugars_g") ?? 99),
    bubble: (a) => ({ big: a.nutriscore.toUpperCase(), small: "Nutri-Score" }),
    why: (a, p) => (p.nutriscore ? `Nutri-Score ${a.nutriscore.toUpperCase()} vs ${p.nutriscore.toUpperCase()}` : `Nutri-Score ${a.nutriscore.toUpperCase()}`),
  },
  {
    key: "sugar", title: "Less sugar", icon: Candy, band: "bg-clay-50 text-clay-700 border-clay-700/15",
    better: (a, p) => isNum(v(a, "total_sugars_g")) && (!isNum(v(p, "total_sugars_g")) || v(a, "total_sugars_g") < v(p, "total_sugars_g")),
    sort: (a, b) => v(a, "total_sugars_g") - v(b, "total_sugars_g"),
    bubble: (a) => ({ big: formatNutrient(v(a, "total_sugars_g"), "g"), small: "sugar / 100 g" }),
    why: (a, p) => (isNum(v(p, "total_sugars_g")) ? `${formatNutrient(Math.round((v(p, "total_sugars_g") - v(a, "total_sugars_g")) * 10) / 10, "g")} less sugar per 100 g` : "Lowest sugar in this category"),
  },
  {
    key: "fibre", title: "More fibre", icon: Wheat, band: "bg-sage-50 text-sage-700 border-sage-700/15",
    better: (a, p) => isNum(v(a, "fibre_g")) && (!isNum(v(p, "fibre_g")) || v(a, "fibre_g") > v(p, "fibre_g")),
    sort: (a, b) => v(b, "fibre_g") - v(a, "fibre_g"),
    bubble: (a) => ({ big: formatNutrient(v(a, "fibre_g"), "g"), small: "fibre / 100 g" }),
    why: (a, p) => (isNum(v(p, "fibre_g")) ? `${formatNutrient(Math.round((v(a, "fibre_g") - v(p, "fibre_g")) * 10) / 10, "g")} more fibre per 100 g` : "Most fibre in this category"),
  },
  {
    key: "additives", title: "Fewer additives", icon: FlaskConical, band: "bg-teal-50 text-teal-700 border-teal-700/15",
    better: (a, p) => a.additives.length < p.additives.length,
    sort: (a, b) => a.additives.length - b.additives.length,
    bubble: (a) => ({ big: String(a.additives.length), small: a.additives.length === 1 ? "additive" : "additives" }),
    why: (a, p) => `${a.additives.length} vs ${p.additives.length} additives listed`,
  },
];

function rankPicks(product, alts) {
  const used = new Set();
  const picks = [];
  for (const c of CRITERIA) {
    const cands = alts.filter((a) => c.better(a, product)).sort(c.sort);
    const pick = cands.find((a) => !used.has(a.code)) || null; // a different product per rank
    if (pick) {
      used.add(pick.code);
      picks.push({ ...c, product: pick });
    }
  }
  return picks;
}

const ROWS = [
  { label: "Nutri-Score", get: (p) => GRADE[p.nutriscore] ?? null, show: (p) => <NutriScore grade={p.nutriscore} size="sm" />, lowerBetter: true },
  { label: "Energy (kcal)", get: (p) => v(p, "energy_kcal"), neutral: true },
  { label: "Sugar (g)", get: (p) => v(p, "total_sugars_g"), lowerBetter: true },
  { label: "Saturated fat (g)", get: (p) => v(p, "saturated_fat_g"), lowerBetter: true },
  { label: "Salt (g)", get: (p) => v(p, "salt_g"), lowerBetter: true },
  { label: "Fibre (g)", get: (p) => v(p, "fibre_g") },
  { label: "Protein (g)", get: (p) => v(p, "protein_g") },
  { label: "Additives", get: (p) => p.additives.length, lowerBetter: true },
  {
    label: "Palm oil", get: (p) => (palm(p) ? 1 : 0), lowerBetter: true,
    show: (p) => (palm(p) ? <span className="inline-flex items-center gap-1 text-clay-700"><Check className="size-4" aria-hidden="true" />Yes</span> : <span className="inline-flex items-center gap-1 text-sage-700"><X className="size-4" aria-hidden="true" />No</span>),
  },
];

function cellTone(row, value, values) {
  if (row.neutral || !isNum(value)) return "";
  const nums = values.filter(isNum);
  if (nums.length < 2) return "";
  const best = row.lowerBetter ? Math.min(...nums) : Math.max(...nums);
  const worst = row.lowerBetter ? Math.max(...nums) : Math.min(...nums);
  if (best === worst) return "";
  if (value === best) return "bg-sage-50 font-semibold text-sage-700";
  if (value === worst) return "bg-clay-50 text-clay-700";
  return "";
}

const FILTERS = [
  { id: "lowsugar", label: "Low sugar (≤ 5 g)", test: (p) => isNum(v(p, "total_sugars_g")) && v(p, "total_sugars_g") <= 5 },
  { id: "highfibre", label: "High fibre (≥ 6 g)", test: (p) => isNum(v(p, "fibre_g")) && v(p, "fibre_g") >= 6 },
  { id: "palmfree", label: "No palm oil", test: (p) => !palm(p) },
  { id: "veg", label: "Vegetarian", test: (p) => !p.analysis.includes("en:non-vegetarian") },
  { id: "noadd", label: "No additives", test: (p) => p.additives.length === 0 },
];

const SORTS = [
  { id: "nutri", label: "Nutri-Score", fn: (a, b) => (GRADE[a.nutriscore] ?? 9) - (GRADE[b.nutriscore] ?? 9) },
  { id: "sugar", label: "Lowest sugar", fn: (a, b) => (v(a, "total_sugars_g") ?? 999) - (v(b, "total_sugars_g") ?? 999) },
  { id: "fibre", label: "Highest fibre", fn: (a, b) => (v(b, "fibre_g") ?? -1) - (v(a, "fibre_g") ?? -1) },
  { id: "protein", label: "Highest protein", fn: (a, b) => (v(b, "protein_g") ?? -1) - (v(a, "protein_g") ?? -1) },
  { id: "additives", label: "Fewest additives", fn: (a, b) => a.additives.length - b.additives.length },
];

export default function AlternativesPanel({ product, country, avoid }) {
  const [sort, setSort] = useState("nutri");
  const [active, setActive] = useState({});
  const [hideAvoided, setHideAvoided] = useState(true);
  const { data, loading, error, retry } = useAsync((signal) => getAlternatives(product, { country, signal }), [product.code, country]);

  const alts = useMemo(() => {
    let list = data?.products ?? [];
    // List results don't include full ingredient lists, so avoid-matching here uses allergens and palm-oil analysis.
    if (hideAvoided && avoid.length) list = list.filter((a) => matchAvoid({ ...a, ingredients: [], ingredientsText: null }, avoid).length === 0);
    for (const f of FILTERS) if (active[f.id]) list = list.filter(f.test);
    return list;
  }, [data, hideAvoided, avoid, active]);
  const picks = useMemo(() => rankPicks(product, alts), [product, alts]);
  const sorted = useMemo(() => [...alts].sort(SORTS.find((s) => s.id === sort).fn), [alts, sort]);
  const columns = useMemo(() => [product, ...picks.map((p) => p.product)], [product, picks]);
  const colKey = columns.map((c) => c.code).join(",");
  const live = useAsync(
    (signal) => Promise.all(columns.map((c) => getLivePrices({ barcode: c.code, query: retailerQuery(c) }, { signal }).catch(() => []))).then((arr) => Object.fromEntries(columns.map((c, i) => [c.code, arr[i]]))),
    [colKey],
    { enabled: priceFeedEnabled && picks.length > 0 }
  );
  const priceOf = (p) => bestOffer(offersFor(p, live.data?.[p.code]));
  const priceRow = {
    label: "Best price / 100 g", lowerBetter: true,
    get: (p) => priceOf(p)?.per100 ?? null,
    show: (p) => {
      const o = priceOf(p);
      if (!o) return <a href={href(`/product/${p.code}`, { tab: "buy" })} className="text-xs font-semibold text-teal-700 hover:underline">Check price</a>;
      return <span>{isNum(o.per100) ? formatPerHundred(o.per100) : formatINR(o.price)}<span className="block text-[11px] font-normal text-ink-500">{o.retailer}</span></span>;
    },
  };

  if (loading) return <div className="grid gap-4 md:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-80" />)}</div>;
  if (error) return <ErrorBox error={error} title="Couldn’t load alternatives" onRetry={retry} />;
  if (!data?.products?.length) {
    return (
      <EmptyState icon={SearchX} title="No comparable products found">
        {product.categoriesHierarchy.length === 0 ? "This product has no category in Open Food Facts, so similar products can’t be matched." : "No other products with nutrition data were found in this category for your country setting."}
      </EmptyState>
    );
  }

  const sugarPick = picks.find((p) => p.key === "sugar");
  const fibrePick = picks.find((p) => p.key === "fibre");
  const top = picks[0];
  const catName = tagLabel(data.category);

  return (
    <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="h-max overflow-hidden rounded-[var(--radius-card)] border border-cream-200 bg-white shadow-card lg:sticky lg:top-36">
        <p className="bg-teal-800 px-4 py-3 font-semibold text-cream-50">Find a better option</p>
        <div className="space-y-5 p-4">
          <fieldset>
            <div className="flex items-center justify-between">
              <legend className="text-sm font-bold">Filters</legend>
              <button type="button" className="text-xs font-semibold text-teal-700 underline" onClick={() => setActive({})}>Reset all</button>
            </div>
            <div className="mt-2 space-y-2">
              {FILTERS.map((f) => (
                <label key={f.id} className="flex items-center gap-2.5 text-sm text-ink-700">
                  <input type="checkbox" className="size-4 accent-teal-700" checked={Boolean(active[f.id])} onChange={(e) => setActive((a) => ({ ...a, [f.id]: e.target.checked }))} />{f.label}
                </label>
              ))}
              {avoid.length > 0 && (
                <label className="flex items-center gap-2.5 text-sm text-ink-700">
                  <input type="checkbox" className="size-4 accent-teal-700" checked={hideAvoided} onChange={(e) => setHideAvoided(e.target.checked)} />Hide my avoided items
                </label>
              )}
            </div>
          </fieldset>
          <fieldset>
            <legend className="text-sm font-bold">Sort list by</legend>
            <div className="mt-2 space-y-2">
              {SORTS.map((s) => (
                <label key={s.id} className="flex items-center gap-2.5 text-sm text-ink-700">
                  <input type="radio" name="alt-sort" className="size-4 accent-teal-700" checked={sort === s.id} onChange={() => setSort(s.id)} />{s.label}
                </label>
              ))}
            </div>
          </fieldset>
          <p className="text-xs text-ink-500">{alts.length} of {data.products.length} products · {catName}</p>
        </div>
      </aside>

      <div className="min-w-0 space-y-6">
        {picks.length === 0 ? (
          <div className="rounded-[var(--radius-card)] border border-dashed border-cream-300 bg-cream-50 p-5 text-sm text-ink-500">
            No alternative beats this product on Nutri-Score, sugar, fibre or additives{Object.values(active).some(Boolean) ? " with these filters" : ""}.
          </div>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4" data-testid="picks">
            {picks.map(({ key, title, icon: Icon, band, bubble, why, product: p }, i) => {
              const b = bubble(p);
              return (
                <li key={key} className="card flex min-w-0 flex-col overflow-hidden">
                  <p className={`flex items-center gap-2 border-b px-4 py-2.5 text-sm font-bold ${band}`}><Icon className="size-4" aria-hidden="true" />#{i + 1} {title}</p>
                  <div className="relative px-4 pt-4">
                    <div className="mx-auto max-w-[170px]"><ProductThumb src={p.image || p.thumb} alt={p.name} size="card" /></div>
                    <span className="absolute bottom-0 right-3 grid size-[4.5rem] place-items-center rounded-full border-4 border-white bg-sage-50 text-center leading-tight shadow-card">
                      <span><span className="block font-display text-base font-semibold text-teal-900">{b.big}</span><span className="block text-[9px] text-ink-500">{b.small}</span></span>
                    </span>
                  </div>
                  <div className="flex flex-1 flex-col p-4">
                    <a href={href(`/product/${p.code}`)} className="font-semibold leading-snug hover:text-teal-700">{p.name}</a>
                    <p className="text-sm text-ink-500">{[p.brand, p.quantity].filter(Boolean).join(" · ")}</p>
                    <p className="mt-2 flex-1 text-sm text-ink-700">{why(p, product)}.</p>
                    {(() => {
                      const o = priceOf(p);
                      return o ? (
                        <p className="mt-2 rounded-xl bg-cream-100 px-3 py-2 text-sm"><span className="font-semibold">{formatINR(o.price)}</span>{isNum(o.per100) && <span className="text-ink-500"> · {formatPerHundred(o.per100)}</span>}<span className="block text-xs text-ink-500">Best price {o.source === "live" ? "from" : "you checked at"} {o.retailer}</span></p>
                      ) : (
                        <p className="mt-2 text-xs text-ink-500">No price checked yet for this product.</p>
                      );
                    })()}
                    <a href={href(`/product/${p.code}`, { tab: "buy" })} className="btn-primary mt-4 w-full"><ShoppingBasket className="size-4" aria-hidden="true" /> Compare prices</a>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        {picks.length > 0 && (
          <section className="card overflow-hidden" aria-labelledby="ntable">
            <h2 id="ntable" className="px-5 pt-5 font-display text-xl font-semibold">Nutritional comparison <span className="text-base font-normal text-ink-500">(per 100 g)</span></h2>
            <div className="overflow-x-auto p-3">
              <table className="w-full min-w-[560px] border-separate border-spacing-0 text-sm">
                <thead>
                  <tr>
                    <th scope="col" className="w-36"><span className="sr-only">Nutrient</span></th>
                    {columns.map((c, i) => (
                      <th key={c.code} scope="col" className={`max-w-[9rem] px-3 py-2 text-left align-bottom text-xs font-semibold ${i === 0 ? "text-teal-700" : "text-ink-700"}`}>
                        {i === 0 ? "This product" : `#${i}`}<span className="block truncate font-normal text-ink-500" title={c.name}>{c.name}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[...ROWS, priceRow].map((row) => {
                    const values = columns.map(row.get);
                    return (
                      <tr key={row.label}>
                        <th scope="row" className="border-t border-cream-200 px-3 py-2 text-left font-semibold">{row.label}</th>
                        {columns.map((c, i) => (
                          <td key={c.code} className={`border-t border-cream-200 px-3 py-2 tabular-nums ${cellTone(row, values[i], values)}`}>
                            {row.show ? row.show(c) : isNum(values[i]) ? values[i] : "—"}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="px-5 pb-4 text-xs text-ink-500">Green = best, red = least good in each row. Nutri-Score is calculated by Open Food Facts. Prices come from what you’ve checked on Where to buy{priceFeedEnabled ? " and the live price service" : ""} — never estimated.</p>
          </section>
        )}

        {picks.length > 0 && (
          <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {top && (
              <li className="card flex gap-3 p-5">
                <span className="grid size-10 shrink-0 place-items-center rounded-full bg-sage-50 text-sage-700"><Lightbulb className="size-5" aria-hidden="true" /></span>
                <div><p className="font-display text-lg font-semibold">Key insight</p><p className="mt-1 text-sm text-ink-700">{top.product.name} is #1 for {top.title.toLowerCase()}: {top.why(top.product, product)}.</p></div>
              </li>
            )}
            {sugarPick && isNum(v(product, "total_sugars_g")) && (
              <li className="card flex gap-3 p-5">
                <span className="grid size-10 shrink-0 place-items-center rounded-full bg-clay-50 text-clay-700"><TrendingDown className="size-5" aria-hidden="true" /></span>
                <div><p className="font-display text-lg font-semibold">Cut sugar</p><p className="mt-1 text-sm text-ink-700">Switching to {sugarPick.product.name} means {formatNutrient(Math.round((v(product, "total_sugars_g") - v(sugarPick.product, "total_sugars_g")) * 0.45 * 10) / 10, "g")} less sugar in a 45 g bowl.</p></div>
              </li>
            )}
            {(() => {
              const mine = priceOf(product);
              const cheaper = picks.map((pk) => ({ pk, o: priceOf(pk.product) })).filter(({ o }) => o && isNum(o.per100) && mine && isNum(mine.per100) && o.per100 < mine.per100).sort((a, b) => a.o.per100 - b.o.per100)[0];
              return cheaper ? (
                <li className="card flex gap-3 p-5">
                  <span className="grid size-10 shrink-0 place-items-center rounded-full bg-amber-50 text-amber-600"><BadgeIndianRupee className="size-5" aria-hidden="true" /></span>
                  <div><p className="font-display text-lg font-semibold">You could save</p><p className="mt-1 text-sm text-ink-700">{cheaper.pk.product.name} is {formatINR(Math.round((mine.per100 - cheaper.o.per100) * 100) / 100, { precise: true })} less per 100 g ({cheaper.o.retailer}) than the best price for this product ({mine.retailer}).</p></div>
                </li>
              ) : null;
            })()}
            {fibrePick && (
              <li className="card flex gap-3 p-5">
                <span className="grid size-10 shrink-0 place-items-center rounded-full bg-teal-50 text-teal-700"><Wheat className="size-5" aria-hidden="true" /></span>
                <div><p className="font-display text-lg font-semibold">More fibre</p><p className="mt-1 text-sm text-ink-700">{fibrePick.product.name} has {fibrePick.why(fibrePick.product, product)}.</p></div>
              </li>
            )}
          </ul>
        )}

        <section aria-labelledby="all-alts">
          <h2 id="all-alts" className="mb-3 font-display text-xl font-semibold">All alternatives <span className="text-base font-normal text-ink-500">· {SORTS.find((s) => s.id === sort).label.toLowerCase()} first</span></h2>
          {sorted.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-cream-300 px-4 py-6 text-center text-sm text-ink-500">No products match these filters.</p>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" data-testid="alt-list">
              {sorted.slice(0, 18).map((p) => (
                <li key={p.code} className="min-w-0">
                  <a href={href(`/product/${p.code}`)} className="card flex items-center gap-3 p-3 hover:shadow-lift">
                    <ProductThumb src={p.thumb} alt={p.name} size="md" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold">{p.name}</span>
                      <span className="block truncate text-xs text-ink-500">{[p.brand, p.quantity].filter(Boolean).join(" · ")}</span>
                      <span className="mt-1.5 flex items-center gap-2 text-xs text-ink-500"><NutriScore grade={p.nutriscore} size="sm" />{isNum(v(p, "total_sugars_g")) && `${formatNutrient(v(p, "total_sugars_g"), "g")} sugar`}</span>
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

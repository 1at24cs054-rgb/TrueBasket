import { useMemo, useState } from "react";
import SizeVariants from "./SizeVariants.jsx";
import { BadgeCheck, ExternalLink, MapPin, Receipt, RotateCcw, Store, Trophy } from "lucide-react";
import { Badge, ErrorBox, Notice, SectionHeading, Spinner } from "./ui.jsx";
import { RETAILERS, retailerQuery } from "../config/retailers.js";
import { useAsync } from "../hooks/useAsync.js";
import { useMyPrices } from "../lib/storage.js";
import { formatDate, formatINR, formatMoney, formatPack, formatPerHundred, isNum, perHundred } from "../lib/format.js";
import { getCommunityPrices, pricesPageUrl } from "../services/openPrices.js";
import { getLivePrices, priceFeedEnabled } from "../services/priceFeed.js";

const PROOF = { PRICE_TAG: "Price-tag photo", RECEIPT: "Receipt", SHOP_IMPORT: "Shop data" };

/** Ranks offers by price per 100 g when every offer has a size, otherwise by total price. */
function rank(offers) {
  const valid = offers.filter((o) => isNum(o.price) && o.price > 0);
  if (valid.length === 0) return { sorted: [], byUnit: false };
  const byUnit = valid.every((o) => isNum(o.per100));
  const key = byUnit ? "per100" : "price";
  return { sorted: [...valid].sort((a, b) => a[key] - b[key]), byUnit };
}

function Summary({ ranking, unit }) {
  const { sorted, byUnit } = ranking;
  if (sorted.length === 0) return null;
  const best = sorted[0];
  const worst = sorted[sorted.length - 1];
  if (sorted.length === 1) {
    return <Notice tone="teal" icon={Receipt} title={`${best.retailer}: ${formatINR(best.price)}`}>Add the price from at least one more store to see which is cheaper.</Notice>;
  }
  const diff = byUnit ? (worst.per100 - best.per100) : worst.price - best.price;
  return (
    <div className="flex flex-col gap-3 rounded-[var(--radius-card)] bg-teal-700 p-5 text-cream-50 sm:flex-row sm:items-center">
      <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-amber-400 text-teal-900"><Trophy className="size-5" aria-hidden="true" /></span>
      <div className="min-w-0">
        <p className="text-xs font-bold uppercase tracking-wider text-teal-100">Cheapest {byUnit ? "per 100 " + unit : "price"}</p>
        <p className="font-display text-2xl font-semibold" data-testid="cheapest">
          {best.retailer} · {formatINR(best.price)}{byUnit && <span className="text-base font-normal text-teal-100"> ({formatPerHundred(best.per100, unit)})</span>}
        </p>
        <p className="mt-0.5 text-sm text-teal-100">
          {diff > 0
            ? byUnit
              ? `${formatINR(Math.round(diff * 100) / 100, { precise: true })} less per 100 ${unit} than ${worst.retailer}.`
              : `${formatINR(diff)} less than ${worst.retailer}.`
            : "Same price at every store you checked."}
          {!byUnit && " Add pack sizes to compare per 100 " + unit + "."}
          {" "}Based on {sorted.length} prices{sorted.some((o) => o.source === "you") ? " you entered" : ""}.
        </p>
      </div>
    </div>
  );
}

export default function WhereToBuy({ product, prefs, onOpenPrefs }) {
  const [withSize, setWithSize] = useState(Boolean(product.quantity));
  const query = retailerQuery(product, { withSize });
  const unit = product.pack?.unit === "ml" ? "ml" : "g";
  const [mine, setMine] = useMyPrices(product.code);

  const live = useAsync((signal) => getLivePrices({ barcode: product.code, query, pincode: prefs.pincode }, { signal }), [product.code, prefs.pincode], { enabled: priceFeedEnabled });
  const community = useAsync((signal) => getCommunityPrices(product.code, { signal }), [product.code]);

  const setEntry = (id, patch) => setMine((m) => ({ ...m, [id]: { ...m[id], ...patch, at: new Date().toISOString() } }));

  const offers = useMemo(() => {
    const out = [];
    for (const r of RETAILERS) {
      const e = mine[r.id];
      const price = e?.price === "" || e?.price === undefined ? null : Number(e.price);
      const size = e?.size === "" || e?.size === undefined ? product.pack?.value ?? null : Number(e.size);
      if (isNum(price)) out.push({ id: r.id, retailer: r.name, price, size, per100: perHundred(price, size ? { value: size } : null), source: "you" });
    }
    for (const l of live.data || []) {
      const size = l.pack_size?.value ?? product.pack?.value ?? null;
      out.push({ id: `live-${l.retailer_id || l.retailer}`, retailer: l.retailer, price: l.price_inr, size, per100: perHundred(l.price_inr, size ? { value: size } : null), source: "live", url: l.url });
    }
    return out;
  }, [mine, live.data, product.pack]);
  const ranking = useMemo(() => rank(offers), [offers]);
  const cheapestId = ranking.sorted.length > 1 ? ranking.sorted[0].id : null;
  const hasMine = Object.values(mine).some((e) => e?.price !== undefined && e?.price !== "");
  const inr = (community.data || []).filter((p) => p.currency === "INR");
  const otherCurrency = (community.data || []).filter((p) => p.currency !== "INR");

  return (
    <div className="space-y-10">
      <section aria-labelledby="stores-heading">
        <SectionHeading id="stores-heading" eyebrow="Where to buy" title="Compare prices across stores"
          description="Open the product on each app, type in the price you see, and TrueBasket works out where it’s cheapest — per pack and per 100 g."
          action={
            <button type="button" onClick={onOpenPrefs} className="btn-secondary">
              <MapPin className="size-4" aria-hidden="true" /> {prefs.pincode ? `Pincode ${prefs.pincode}` : "Set pincode"}
            </button>
          } />

        <div className="mb-4 space-y-3">
          <Summary ranking={ranking} unit={unit} />
          {!hasMine && !live.data?.length && (
            <Notice tone="slate" icon={Store} title="Why can’t TrueBasket fetch these prices automatically?">
              Blinkit, Instamart, Zepto, BigBasket, DMart and JioMart don’t offer public price APIs, and their prices change by pincode. So we open the product on each store for you instead of guessing a price.
            </Notice>
          )}
        </div>

        <div className="overflow-hidden rounded-[var(--radius-card)] border border-cream-200 bg-cream-50/60">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-cream-200 bg-white px-5 py-3">
            <p className="flex items-center gap-2 font-display text-lg font-semibold"><Store className="size-5 text-teal-700" aria-hidden="true" /> Buy from Indian stores</p>
            <p className="text-xs text-ink-500">Prices open on each store’s own app or site</p>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-cream-200 bg-white px-5 py-3">
            <SizeVariants product={product} tab="buy" label="Size" />
            {product.quantity && (
              <label className="flex items-center gap-2 text-sm text-ink-700">
                <input type="checkbox" className="size-4 accent-teal-700" checked={withSize} onChange={(e) => setWithSize(e.target.checked)} />
                Search stores for {product.quantity} only
              </label>
            )}
          </div>
          <div className="hidden price-grid items-center gap-4 px-6 pt-3 text-[11px] font-bold uppercase tracking-wider text-ink-400 md:grid">
            <span>Store</span><span>Price you see</span><span>Pack ({unit})</span><span className="text-right">Per 100 {unit}</span><span />
          </div>
          <ul className="space-y-3 p-3">
            {RETAILERS.map((r) => {
              const e = mine[r.id] || {};
              const offer = offers.find((o) => o.id === r.id);
              const isCheapest = cheapestId === r.id;
              return (
                <li key={r.id} className={`relative grid price-grid items-center gap-x-4 gap-y-3 rounded-2xl border bg-white px-4 py-4 shadow-card transition-colors sm:px-5 ${isCheapest ? "border-sage-700/40 ring-2 ring-sage-700/20" : "border-cream-200"}`}>
                  {isCheapest && <span className="absolute -top-2.5 left-4 rounded-md bg-sage-700 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-white">Best deal</span>}
                  <div className="col-span-2 flex min-w-0 items-center gap-3 md:col-span-1">
                    <span className="grid size-12 shrink-0 place-items-center rounded-2xl font-display text-xl font-semibold text-white" style={{ background: r.color }} aria-hidden="true">{r.name[0]}</span>
                    <div className="min-w-0">
                      <p className="flex flex-wrap items-center gap-2 font-semibold">{r.name}{isCheapest && <Badge tone="sage" icon={Trophy}>Cheapest</Badge>}</p>
                      <p className="text-xs text-ink-500">{r.kind} · {r.eta}</p>
                    </div>
                  </div>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-ink-500 md:sr-only">Price you see (₹)</span>
                    <span className="relative block">
                      <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-ink-400">₹</span>
                      <input type="number" inputMode="decimal" min="0" step="0.5" className="field-input py-2 pl-7 font-semibold" placeholder="—"
                        aria-label={`Price on ${r.name} in rupees`} value={e.price ?? ""}
                        onChange={(ev) => setEntry(r.id, { price: ev.target.value })} />
                    </span>
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-xs font-semibold text-ink-500 md:sr-only">Pack ({unit})</span>
                    <input type="number" inputMode="numeric" min="1" className="field-input py-2" placeholder={product.pack?.value ? String(product.pack.value) : unit}
                      aria-label={`Pack size on ${r.name} in ${unit}`} value={e.size ?? ""}
                      onChange={(ev) => setEntry(r.id, { size: ev.target.value })} />
                  </label>
                  <p className="text-sm tabular-nums md:text-right">
                    <span className="text-ink-500 md:hidden">Per 100 {unit}: </span>
                    {offer && isNum(offer.per100) ? <span className={`font-display text-lg font-semibold ${isCheapest ? "text-sage-700" : ""}`}>{formatPerHundred(offer.per100, unit)}</span> : <span className="text-ink-400">—</span>}
                  </p>
                  <a href={r.search(query)} target="_blank" rel="noopener noreferrer" className="btn-primary px-4 py-2.5">
                    Open on {r.name.split(" ")[0]} <ExternalLink className="size-3.5" aria-hidden="true" />
                    <span className="sr-only">(opens {r.name} search in a new tab)</span>
                  </a>
                </li>
              );
            })}
          </ul>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-cream-200 px-5 py-3 text-xs text-ink-500">
            <span>
              Searching for “{query}”. {product.pack ? `Default pack: ${formatPack(product.pack)}.` : "Pack size unknown — enter it to compare per 100 " + unit + "."} Prices you enter stay on this device.
            </span>
            {hasMine && (
              <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={() => setMine({})}>
                <RotateCcw className="size-3.5" aria-hidden="true" /> Clear my prices
              </button>
            )}
          </div>
        </div>
      </section>

      {priceFeedEnabled && (
        <section aria-labelledby="live-heading">
          <SectionHeading id="live-heading" eyebrow="Live prices" title="From the TrueBasket price service" />
          {live.loading ? <Spinner label="Checking live prices…" /> : live.error ? <ErrorBox error={live.error} title="Live prices unavailable" onRetry={live.retry} /> : !live.data?.length ? (
            <p className="text-sm text-ink-500">No live listings were returned for this product{prefs.pincode ? ` at pincode ${prefs.pincode}` : ""}.</p>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {live.data.map((l) => (
                <li key={`${l.retailer}-${l.price_inr}`} className="card p-4">
                  <p className="flex items-center gap-2 font-semibold"><BadgeCheck className="size-4 text-sage-700" aria-hidden="true" />{l.retailer}</p>
                  <p className="mt-2 font-display text-2xl font-semibold">{formatINR(l.price_inr)}{isNum(l.mrp_inr) && l.mrp_inr > l.price_inr && <span className="ml-2 text-sm font-normal text-ink-400 line-through">{formatINR(l.mrp_inr)}</span>}</p>
                  <p className="text-sm text-ink-500">{[formatPack(l.pack_size), l.in_stock === false ? "Out of stock" : l.in_stock ? "In stock" : null, l.checked_at ? `checked ${formatDate(l.checked_at)}` : null].filter(Boolean).join(" · ")}</p>
                  {l.url && <a className="btn-primary mt-3 w-full" href={l.url} target="_blank" rel="noopener noreferrer">Buy on {l.retailer} <ExternalLink className="size-4" aria-hidden="true" /></a>}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section aria-labelledby="community-heading">
        <SectionHeading id="community-heading" eyebrow="Reported prices" title="Prices seen by shoppers"
          description="Real prices submitted to Open Prices with a photo of the price tag or receipt."
          action={<a className="btn-ghost" href={pricesPageUrl(product.code)} target="_blank" rel="noopener noreferrer">Add a price <ExternalLink className="size-4" aria-hidden="true" /></a>} />
        {community.loading ? <Spinner label="Loading reported prices…" /> : community.error ? (
          <ErrorBox error={community.error} title="Couldn’t load reported prices" onRetry={community.retry} />
        ) : !community.data?.length ? (
          <p className="rounded-2xl border border-dashed border-cream-300 px-4 py-6 text-center text-sm text-ink-500">No one has reported a price for this product yet. You can be the first on Open Prices.</p>
        ) : (
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="bg-cream-50 text-left text-xs font-bold uppercase tracking-wider text-ink-400">
                  <th scope="col" className="px-5 py-2.5">Store</th><th scope="col" className="px-3 py-2.5">Price</th><th scope="col" className="px-3 py-2.5">Date</th><th scope="col" className="px-5 py-2.5">Proof</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cream-200">
                {[...inr, ...otherCurrency].map((p) => (
                  <tr key={p.id}>
                    <td className="px-5 py-2.5"><span className="font-semibold">{p.store || "Unnamed store"}</span><span className="block text-xs text-ink-500">{[p.online ? "Online" : null, p.city, p.country].filter(Boolean).join(", ")}</span></td>
                    <td className="px-3 py-2.5 font-semibold tabular-nums">{formatMoney(p.price, p.currency)}{p.discounted && <Badge tone="sage" className="ml-2">Discounted</Badge>}</td>
                    <td className="px-3 py-2.5 text-ink-700">{formatDate(p.date) || "—"}</td>
                    <td className="px-5 py-2.5 text-ink-500">{PROOF[p.proofType] || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {product.stores.length > 0 && (
        <p className="text-sm text-ink-500"><span className="font-semibold text-ink-700">Stores where shoppers have seen it:</span> {product.stores.join(", ")} <span className="text-ink-400">(Open Food Facts)</span></p>
      )}
    </div>
  );
}

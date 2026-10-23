import { Scale } from "lucide-react";
import { useAsync } from "../hooks/useAsync.js";
import { getSizeVariants } from "../services/openFoodFacts.js";
import { formatPack } from "../lib/format.js";
import { href } from "../lib/router.js";

/** Pack-size chips for the same product. Each size is its own barcode and price. */
export default function SizeVariants({ product, tab, label = "Pack sizes" }) {
  const { data } = useAsync((signal) => getSizeVariants(product, { signal }), [product.code]);
  if (!data || data.length < 2) return null;
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="size-variants">
      <span className="flex items-center gap-1.5 text-sm font-semibold text-ink-700"><Scale className="size-4 text-teal-600" aria-hidden="true" />{label}:</span>
      {data.map((v) => {
        const current = v.code === product.code;
        return current ? (
          <span key={v.code} aria-current="true" className="rounded-full bg-teal-700 px-3 py-1 text-sm font-semibold text-cream-50">{formatPack(v.pack)}</span>
        ) : (
          <a key={v.code} href={href(`/product/${v.code}`, tab ? { tab } : null)} className="rounded-full border border-cream-300 bg-white px-3 py-1 text-sm font-semibold text-ink-700 hover:border-teal-200 hover:bg-teal-50">{formatPack(v.pack)}</a>
        );
      })}
    </div>
  );
}

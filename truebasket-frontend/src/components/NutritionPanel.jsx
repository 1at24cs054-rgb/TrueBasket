import { AlertCircle, BarChart3, CheckCircle2, Lightbulb } from "lucide-react";
import { NUTRIENTS, formatNutrient, isNum } from "../lib/format.js";
import { nutritionInsights } from "../lib/ingredientInfo.js";

/** Nutrition per 100 g/ml and per serving, plus threshold-based insights. */
export default function NutritionPanel({ product }) {
  const per100 = product.per100 || {};
  const perServing = product.perServing || {};
  const hasServing = Object.values(perServing).some(isNum);
  const unit = product.pack?.unit === "ml" ? "ml" : "g";
  const rows = NUTRIENTS.filter((n) => n.key !== "added_sugars_g" || isNum(per100.added_sugars_g));
  const anyValue = rows.some((n) => isNum(per100[n.key]));
  const insights = nutritionInsights(per100);

  return (
    <section className="card overflow-hidden" aria-labelledby="nutrition-heading">
      <div className="flex items-center gap-3 px-5 pb-2 pt-5">
        <BarChart3 className="size-6 text-teal-700" aria-hidden="true" />
        <div>
          <h2 id="nutrition-heading" className="font-display text-xl font-semibold">Nutrition information</h2>
          <p className="text-xs text-ink-500">Per 100 {unit}{hasServing && product.servingSize ? ` · serving ${product.servingSize}` : ""}</p>
        </div>
      </div>

      {!anyValue ? (
        <p className="px-5 py-8 text-center text-sm text-ink-500">
          {product.noNutritionData ? "This product has no nutrition table on its pack." : "Nutrition values haven’t been added for this product yet."}
        </p>
      ) : (
        <table className="w-full text-sm">
          <caption className="sr-only">Nutrition information</caption>
          <thead className="sr-only">
            <tr><th scope="col">Nutrient</th><th scope="col">Per 100 {unit}</th>{hasServing && <th scope="col">Per serving</th>}</tr>
          </thead>
          <tbody>
            {rows.map((n) => {
              const v = formatNutrient(per100[n.key], n.unit);
              const warn = (n.key === "added_sugars_g" && per100.added_sugars_g > 0) || (n.key === "total_sugars_g" && per100.total_sugars_g > 22.5) || (n.key === "saturated_fat_g" && per100.saturated_fat_g > 5);
              return (
                <tr key={n.key} className={warn ? "bg-clay-50" : ""}>
                  <th scope="row" className={`px-5 py-2 text-left font-medium ${n.indent ? "pl-9 text-ink-500" : "text-ink-900"}`}>{n.indent ? n.label : n.label}</th>
                  <td className={`px-3 py-2 text-right font-semibold tabular-nums ${warn ? "text-clay-700" : ""}`}>{v ?? <span className="font-normal text-ink-400">—</span>}</td>
                  {hasServing && <td className="px-5 py-2 text-right tabular-nums text-ink-500">{formatNutrient(perServing[n.key], n.unit) ?? "—"}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {insights.length > 0 && (
        <div className="m-4 rounded-2xl bg-sage-50 p-4">
          <p className="flex items-center gap-2 font-display text-lg font-semibold text-teal-900"><Lightbulb className="size-5 text-teal-700" aria-hidden="true" /> Nutrition insights</p>
          <ul className="mt-2 space-y-1.5 text-sm text-ink-700">
            {insights.map((i) => (
              <li key={i.text} className="flex items-start gap-2">
                {i.good ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-sage-700" aria-hidden="true" /> : <AlertCircle className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden="true" />}
                {i.text}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-ink-500">Thresholds: EU nutrition-claim rules and UK front-of-pack guidance, per 100 g.</p>
        </div>
      )}
      <p className="px-5 pb-4 text-xs text-ink-500">From the pack’s nutrition table via Open Food Facts. “—” means not recorded.</p>
    </section>
  );
}

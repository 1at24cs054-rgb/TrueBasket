import { ExternalLink, FlaskConical } from "lucide-react";
import { Badge, Spinner } from "./ui.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { describeAdditive, loadAdditivesTaxonomy } from "../services/openFoodFacts.js";

const RISK = {
  high: { tone: "clay", label: "EFSA: high risk of over-exposure for some groups" },
  moderate: { tone: "amber", label: "EFSA: moderate risk of over-exposure for some groups" },
  no: { tone: "sage", label: "EFSA: no over-exposure risk identified" },
};

/** Additives with names, functions and EFSA evaluations from the OFF taxonomy. */
export default function AdditivesPanel({ additives }) {
  const { data: taxonomy, loading, error } = useAsync(() => loadAdditivesTaxonomy(), [], { enabled: additives.length > 0 });

  return (
    <section className="card overflow-hidden" aria-labelledby="add-heading">
      <div className="flex items-center justify-between border-b border-cream-200 px-5 py-4">
        <h2 id="add-heading" className="font-display text-lg font-semibold">Additives</h2>
        <span className="text-sm text-ink-500">{additives.length}</span>
      </div>
      {additives.length === 0 ? (
        <p className="px-5 py-6 text-sm text-ink-500">No additives are listed for this product.</p>
      ) : loading ? (
        <Spinner label="Loading additive details…" />
      ) : (
        <ul className="divide-y divide-cream-200">
          {additives.map((tag) => {
            const a = describeAdditive(tag, taxonomy);
            const risk = RISK[a.overexposureRisk];
            return (
              <li key={tag} className="px-5 py-4">
                <div className="flex items-start gap-3">
                  <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-teal-50 text-teal-700"><FlaskConical className="size-4" aria-hidden="true" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold">{a.name}</p>
                    {a.classes.length > 0 && <p className="text-sm capitalize text-ink-500">{a.classes.join(", ")}</p>}
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {risk && <Badge tone={risk.tone} dot>{risk.label}</Badge>}
                      {a.vegan === "no" && <Badge tone="slate">Not vegan</Badge>}
                    </div>
                    {a.efsaUrl && (
                      <a href={a.efsaUrl} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-teal-700 hover:underline">
                        EFSA evaluation{a.efsaDate ? ` (${a.efsaDate.slice(0, 4)})` : ""} <ExternalLink className="size-3" aria-hidden="true" />
                      </a>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
      {error && <p className="border-t border-cream-200 px-5 py-3 text-xs text-ink-500">Additive details couldn’t be loaded ({error.message}). Codes are still shown.</p>}
      <p className="border-t border-cream-200 px-5 py-3 text-xs text-ink-500">
        Permitted additives are approved for use within limits. An over-exposure note refers to total intake across all foods, not this product alone. Not medical advice.
      </p>
    </section>
  );
}

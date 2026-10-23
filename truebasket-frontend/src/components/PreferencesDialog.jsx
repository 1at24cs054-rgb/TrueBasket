import { useEffect, useRef, useState } from "react";
import { MapPin, Plus, X } from "lucide-react";
import { COUNTRIES } from "../services/openFoodFacts.js";
import { usePrefs } from "../lib/storage.js";

const SUGGESTED = ["Palm oil", "Sugar", "Maltodextrin", "Artificial flavour", "Gluten", "Milk", "Soy", "Peanuts"];

/** Country, pincode and avoid list — saved on this device. */
export default function PreferencesDialog({ open, onClose }) {
  const ref = useRef(null);
  const [prefs, setPrefs] = usePrefs();
  const [draft, setDraft] = useState("");

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal?.();
    if (!open && d.open) d.close?.();
  }, [open]);

  const add = (term) => {
    const t = term.trim();
    if (!t) return;
    setPrefs((p) => (p.avoid.some((a) => a.toLowerCase() === t.toLowerCase()) ? p : { ...p, avoid: [...p.avoid, t].slice(0, 20) }));
    setDraft("");
  };
  const remove = (t) => setPrefs((p) => ({ ...p, avoid: p.avoid.filter((a) => a !== t) }));
  const pinError = prefs.pincode && !/^\d{6}$/.test(prefs.pincode) ? "Enter a 6-digit pincode." : null;

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-labelledby="prefs-title"
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-[var(--radius-card)] bg-white p-0 text-ink-900 shadow-lift backdrop:bg-ink-900/40"
    >
      <div className="flex items-center justify-between border-b border-cream-200 px-5 py-4">
        <h2 id="prefs-title" className="font-display text-xl font-semibold">Your preferences</h2>
        <button type="button" onClick={onClose} className="grid size-9 place-items-center rounded-lg hover:bg-cream-100" aria-label="Close preferences">
          <X className="size-5" />
        </button>
      </div>

      <div className="space-y-6 px-5 py-5">
        <div>
          <label htmlFor="pref-country" className="field-label">Show products sold in</label>
          <select id="pref-country" className="field-input" value={prefs.country} onChange={(e) => setPrefs((p) => ({ ...p, country: e.target.value }))}>
            {COUNTRIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
          </select>
          <p className="mt-1.5 text-xs text-ink-500">Used for search results and alternatives.</p>
        </div>

        <div>
          <label htmlFor="pref-pin" className="field-label">Delivery pincode <span className="font-normal text-ink-400">(optional)</span></label>
          <div className="relative">
            <MapPin className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-ink-400" aria-hidden="true" />
            <input id="pref-pin" inputMode="numeric" maxLength={6} className="field-input pl-9" placeholder="e.g. 560001" value={prefs.pincode}
              onChange={(e) => setPrefs((p) => ({ ...p, pincode: e.target.value.replace(/\D/g, "") }))} aria-invalid={Boolean(pinError)} />
          </div>
          {pinError ? <p className="mt-1.5 text-sm text-clay-700">{pinError}</p> : <p className="mt-1.5 text-xs text-ink-500">Quick-commerce prices and stock change by pincode. Set the same pincode in each retailer’s app.</p>}
        </div>

        <div>
          <label htmlFor="pref-avoid" className="field-label">Ingredients to avoid</label>
          <div className="flex gap-2">
            <input id="pref-avoid" className="field-input" value={draft} maxLength={40} placeholder="Type and press Enter"
              onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(draft); } }} />
            <button type="button" className="btn-secondary shrink-0" onClick={() => add(draft)} disabled={!draft.trim()} aria-label="Add ingredient to avoid">
              <Plus className="size-4" aria-hidden="true" />
            </button>
          </div>
          {prefs.avoid.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-2" aria-label="Ingredients you avoid">
              {prefs.avoid.map((a) => (
                <li key={a}>
                  <span className="inline-flex items-center gap-1 rounded-full bg-teal-700 py-1 pl-3 pr-1 text-sm font-semibold text-cream-50">
                    {a}
                    <button type="button" onClick={() => remove(a)} className="grid size-5 place-items-center rounded-full hover:bg-teal-900" aria-label={`Remove ${a}`}>
                      <X className="size-3.5" aria-hidden="true" />
                    </button>
                  </span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex flex-wrap gap-1.5">
            {SUGGESTED.filter((s) => !prefs.avoid.some((a) => a.toLowerCase() === s.toLowerCase())).map((s) => (
              <button key={s} type="button" onClick={() => add(s)} className="rounded-full border border-cream-300 bg-white px-2.5 py-0.5 text-xs font-medium text-ink-700 hover:border-teal-200 hover:bg-teal-50">+ {s}</button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex justify-end border-t border-cream-200 px-5 py-4">
        <button type="button" className="btn-primary" onClick={onClose}>Done</button>
      </div>
    </dialog>
  );
}

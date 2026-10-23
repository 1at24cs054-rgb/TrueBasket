import { AlertOctagon, Database, Info, Loader2, RotateCcw, ScanText } from "lucide-react";

const TONES = {
  sage: "bg-sage-50 text-sage-700 ring-sage-700/15",
  amber: "bg-amber-50 text-amber-600 ring-amber-600/20",
  clay: "bg-clay-50 text-clay-700 ring-clay-700/15",
  slate: "bg-slate-50 text-ink-500 ring-ink-500/15",
  teal: "bg-teal-50 text-teal-700 ring-teal-700/15",
};
const DOTS = { sage: "bg-sage-700", amber: "bg-amber-600", clay: "bg-clay-700", slate: "bg-ink-400", teal: "bg-teal-600" };

export function Badge({ tone = "slate", dot = false, icon: Icon, children, className = "" }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${TONES[tone]} ${className}`}>
      {dot && <span className={`size-1.5 rounded-full ${DOTS[tone]}`} aria-hidden="true" />}
      {Icon && <Icon className="size-3.5" aria-hidden="true" />}
      {children}
    </span>
  );
}

/** Where a fact came from. */
export function SourceTag({ source }) {
  if (source === "label") return <Badge tone="teal" icon={ScanText}>From label</Badge>;
  if (source === "off") return <Badge tone="slate" icon={Database}>Open Food Facts</Badge>;
  return null;
}

export function Missing({ children = "Not available" }) {
  return <span className="text-sm italic text-ink-400">{children}</span>;
}

export function SectionHeading({ eyebrow, title, description, action, id }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        {eyebrow && <p className="eyebrow mb-1.5">{eyebrow}</p>}
        <h2 id={id} className="font-display text-2xl font-semibold tracking-tight text-ink-900 sm:text-[1.7rem]">{title}</h2>
        {description && <p className="mt-1.5 max-w-2xl text-sm text-ink-500">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function EmptyState({ icon: Icon = Info, title, children, action }) {
  return (
    <div className="card flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-4 grid size-12 place-items-center rounded-2xl bg-cream-100 text-teal-700">
        <Icon className="size-6" aria-hidden="true" />
      </div>
      <h3 className="font-display text-lg font-semibold">{title}</h3>
      {children && <div className="mt-2 max-w-md text-sm text-ink-500">{children}</div>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Notice({ tone = "slate", icon: Icon = Info, title, children }) {
  const border = { amber: "border-amber-600/25 bg-amber-50", clay: "border-clay-700/20 bg-clay-50", slate: "border-cream-300 bg-cream-50", teal: "border-teal-200 bg-teal-50" }[tone];
  const iconColor = { amber: "text-amber-600", clay: "text-clay-700", slate: "text-ink-500", teal: "text-teal-700" }[tone];
  return (
    <div className={`flex gap-3 rounded-2xl border px-4 py-3 text-sm ${border}`} role="note">
      <Icon className={`mt-0.5 size-4 shrink-0 ${iconColor}`} aria-hidden="true" />
      <div className="min-w-0 text-ink-700">
        {title && <p className="font-semibold text-ink-900">{title}</p>}
        {children}
      </div>
    </div>
  );
}

export function ErrorBox({ error, onRetry, title = "Something went wrong" }) {
  if (!error) return null;
  return (
    <div role="alert" className="rounded-[var(--radius-card)] border border-clay-700/20 bg-clay-50 p-5">
      <div className="flex items-start gap-3">
        <AlertOctagon className="mt-0.5 size-5 shrink-0 text-clay-700" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-ink-900">{title}</p>
          <p className="mt-1 break-words text-sm text-ink-700">{error.message}</p>
          {onRetry && (
            <button type="button" onClick={onRetry} className="btn-primary mt-4">
              <RotateCcw className="size-4" aria-hidden="true" /> Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function Spinner({ label = "Loading…", className = "" }) {
  return (
    <div className={`flex items-center justify-center gap-2 py-10 text-sm text-ink-500 ${className}`} role="status" aria-live="polite">
      <Loader2 className="size-4 animate-spin text-teal-600" aria-hidden="true" />
      {label}
    </div>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={`animate-pulse rounded-xl bg-cream-200/70 ${className}`} aria-hidden="true" />;
}

export function ProductThumb({ src, alt, size = "md" }) {
  const dims = { sm: "size-12", md: "size-16", lg: "size-28 sm:size-32", card: "aspect-square w-full" }[size];
  if (src) {
    return <img src={src} alt={alt} loading="lazy" className={`${dims} shrink-0 rounded-xl border border-cream-200 bg-white object-contain`} />;
  }
  const initials = (alt || "?").split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return (
    <div className={`${dims} grid shrink-0 place-items-center rounded-xl border border-cream-200 bg-cream-100 font-display text-base font-semibold text-teal-700`} role="img" aria-label={`${alt} (no image)`}>
      {initials}
    </div>
  );
}

// ---------------------------------------------------------------- scores

const NUTRI_COLORS = { a: "#1e8f4e", b: "#7ac143", c: "#f5c400", d: "#ef8200", e: "#e63e11" };

/** Nutri-Score as computed by Open Food Facts (the official EU-style algorithm). */
export function NutriScore({ grade, size = "md" }) {
  if (!grade) {
    return <span className="inline-flex items-center rounded-lg bg-cream-100 px-2 py-1 text-xs font-semibold text-ink-400">Nutri-Score unknown</span>;
  }
  const small = size === "sm";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg bg-white px-1.5 py-1 ring-1 ring-cream-300" aria-label={`Nutri-Score ${grade.toUpperCase()}`} title="Nutri-Score, calculated by Open Food Facts">
      {!small && <span className="pl-0.5 text-[10px] font-bold uppercase tracking-wider text-ink-500">Nutri-Score</span>}
      <span className="flex" aria-hidden="true">
        {["a", "b", "c", "d", "e"].map((g) => (
          <span
            key={g}
            className={`grid place-items-center font-bold uppercase text-white ${g === grade ? (small ? "size-5 rounded text-[11px]" : "size-6 rounded-md text-xs") : small ? "h-5 w-3 text-[0px]" : "h-6 w-4 text-[0px]"}`}
            style={{ background: NUTRI_COLORS[g], opacity: g === grade ? 1 : 0.35 }}
          >
            {g}
          </span>
        ))}
      </span>
    </span>
  );
}

const NOVA_LABEL = { 1: "Unprocessed", 2: "Processed ingredient", 3: "Processed", 4: "Ultra-processed" };
const NOVA_TONE = { 1: "sage", 2: "sage", 3: "amber", 4: "clay" };

export function Nova({ group }) {
  if (!group) return <Badge tone="slate">NOVA unknown</Badge>;
  return (
    <Badge tone={NOVA_TONE[group]} className="whitespace-nowrap">
      NOVA {group} · {NOVA_LABEL[group]}
    </Badge>
  );
}

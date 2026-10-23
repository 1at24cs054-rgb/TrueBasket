import { Clock, House, LayoutGrid, MapPin, ScanLine, Scale, SlidersHorizontal, Store } from "lucide-react";
import SearchBar from "./SearchBar.jsx";
import { LeafSprig, Logo, Script } from "./art.jsx";
import { href } from "../lib/router.js";
import { usePrefs, useRecent } from "../lib/storage.js";

function navItems(recent) {
  const last = recent[0];
  return [
    { to: href("/"), id: "/", label: "Home", icon: House },
    { to: href("/scan"), id: "/scan", label: "Scan & Upload", icon: ScanLine },
    { to: href("/categories"), id: "/categories", label: "Browse categories", icon: LayoutGrid },
    { to: last ? href(`/product/${last.code}`, { tab: "alternatives" }) : null, id: "compare", label: "Compare products", icon: Scale, hint: "Open a product first" },
    { to: last ? href(`/product/${last.code}`, { tab: "buy" }) : null, id: "buy", label: "Where to buy", icon: Store, hint: "Open a product first" },
    { to: href("/recent"), id: "/recent", label: "Recently viewed", icon: Clock, badge: recent.length || null },
  ];
}

function activeId(path, tab) {
  if (path.startsWith("/product/")) return tab === "alternatives" ? "compare" : tab === "buy" ? "buy" : null;
  if (path === "/search") return "/categories";
  return path;
}

export function Sidebar({ path, tab, onOpenPrefs }) {
  const [recent] = useRecent();
  const current = activeId(path, tab);
  return (
    <aside className="sticky top-0 hidden h-dvh w-[264px] shrink-0 flex-col overflow-y-auto bg-teal-800 px-4 py-6 text-cream-50 lg:flex">
      <a href={href("/")} className="px-2" aria-label="TrueBasket home"><Logo light /></a>
      <nav aria-label="Main" className="mt-8">
        <ul className="space-y-1">
          {navItems(recent).map(({ to, id, label, icon: Icon, hint, badge }) => (
            <li key={id}>
              {to ? (
                <a href={to} aria-current={current === id ? "page" : undefined}
                  className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-medium transition-colors ${current === id ? "bg-teal-600/60 text-white" : "text-teal-100 hover:bg-teal-700 hover:text-white"}`}>
                  <Icon className="size-5" aria-hidden="true" /> {label}
                  {badge ? <span className="ml-auto rounded-full bg-teal-600 px-2 text-xs font-bold">{badge}</span> : null}
                </a>
              ) : (
                <span className="flex cursor-not-allowed items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-medium text-teal-100/45" title={hint}>
                  <Icon className="size-5" aria-hidden="true" /> {label}
                </span>
              )}
            </li>
          ))}
          <li>
            <button type="button" onClick={onOpenPrefs} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[15px] font-medium text-teal-100 transition-colors hover:bg-teal-700 hover:text-white">
              <SlidersHorizontal className="size-5" aria-hidden="true" /> Preferences
            </button>
          </li>
        </ul>
      </nav>
      <div className="relative mt-auto overflow-hidden rounded-2xl border border-teal-600/60 bg-teal-900/40 p-5 pt-16">
        <LeafSprig className="absolute -right-3 -top-3 h-28 rotate-12" tone="dark" />
        <Script className="text-[1.65rem] text-cream-50">Better food,<br />brighter days.</Script>
        <p className="mt-3 text-sm text-teal-100">Real ingredients. Real prices. No paid rankings.</p>
      </div>
    </aside>
  );
}

export function TopBar({ onOpenPrefs }) {
  const [prefs] = usePrefs();
  return (
    <header className="sticky top-0 z-30 border-b border-cream-200 bg-cream-100/90 backdrop-blur-md">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
        <a href={href("/")} className="shrink-0 lg:hidden" aria-label="TrueBasket home"><Logo /></a>
        <div className="hidden min-w-0 flex-1 md:block"><SearchBar size="sm" /></div>
        <div className="ml-auto flex items-center gap-2">
          <button type="button" onClick={onOpenPrefs} className="btn-secondary hidden px-3 py-2 sm:inline-flex">
            <MapPin className="size-4 text-teal-600" aria-hidden="true" /> {prefs.pincode ? `Deliver to ${prefs.pincode}` : "Set pincode"}
          </button>
          <button type="button" onClick={onOpenPrefs} className="btn-secondary px-3 py-2" aria-label="Preferences">
            <SlidersHorizontal className="size-4" aria-hidden="true" />
            <span className="hidden xl:inline">Preferences</span>
            {prefs.avoid.length > 0 && <span className="rounded-full bg-teal-700 px-1.5 text-[11px] font-bold text-cream-50">{prefs.avoid.length}</span>}
          </button>
        </div>
      </div>
      <div className="px-4 pb-3 md:hidden"><SearchBar size="sm" /></div>
    </header>
  );
}

export function MobileTabBar({ path, onOpenPrefs }) {
  const item = (to, label, Icon, active) => (
    <a href={to} aria-current={active ? "page" : undefined} className={`flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-semibold ${active ? "text-teal-700" : "text-ink-500"}`}>
      <Icon className="size-5" aria-hidden="true" /> {label}
    </a>
  );
  return (
    <nav aria-label="Quick navigation" className="fixed inset-x-0 bottom-0 z-40 border-t border-cream-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
      <div className="mx-auto flex max-w-md items-end px-2">
        {item(href("/"), "Home", House, path === "/")}
        {item(href("/categories"), "Browse", LayoutGrid, path === "/categories" || path === "/search")}
        <a href={href("/scan")} className="-mt-6 flex flex-1 flex-col items-center gap-1 pb-2 text-[11px] font-semibold text-teal-700" aria-label="Scan a product">
          <span className="grid size-14 place-items-center rounded-full bg-teal-700 text-cream-50 shadow-lift ring-4 ring-cream-100"><ScanLine className="size-6" aria-hidden="true" /></span>
          Scan
        </a>
        {item(href("/recent"), "Recent", Clock, path === "/recent")}
        <button type="button" onClick={onOpenPrefs} className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px] font-semibold text-ink-500">
          <SlidersHorizontal className="size-5" aria-hidden="true" /> Prefs
        </button>
      </div>
    </nav>
  );
}

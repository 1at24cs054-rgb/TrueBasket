import { useState } from "react";
import { SearchX } from "lucide-react";
import { MobileTabBar, Sidebar, TopBar } from "./components/AppShell.jsx";
import PreferencesDialog from "./components/PreferencesDialog.jsx";
import { EmptyState } from "./components/ui.jsx";
import HomePage from "./pages/HomePage.jsx";
import SearchPage from "./pages/SearchPage.jsx";
import ScanPage from "./pages/ScanPage.jsx";
import ProductPage from "./pages/ProductPage.jsx";
import { CategoriesPage, RecentPage } from "./pages/BrowsePages.jsx";
import { href, useRoute } from "./lib/router.js";

export default function App() {
  const { path, params } = useRoute();
  const [prefsOpen, setPrefsOpen] = useState(false);
  const openPrefs = () => setPrefsOpen(true);

  let page;
  const productMatch = path.match(/^\/product\/([^/]+)$/);
  if (path === "/") page = <HomePage />;
  else if (path === "/search" && params.q) page = <SearchPage query={params.q} />;
  else if (path === "/scan") page = <ScanPage />;
  else if (path === "/categories") page = <CategoriesPage />;
  else if (path === "/recent") page = <RecentPage />;
  else if (productMatch) page = <ProductPage key={productMatch[1]} code={decodeURIComponent(productMatch[1])} tab={params.tab} via={params.via} onOpenPrefs={openPrefs} />;
  else page = (
    <EmptyState icon={SearchX} title="Page not found" action={<a className="btn-primary" href={href("/")}>Go home</a>}>That link doesn’t lead anywhere.</EmptyState>
  );

  return (
    <div className="flex min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-white focus:px-4 focus:py-2">Skip to content</a>
      <Sidebar path={path} tab={params.tab} onOpenPrefs={openPrefs} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onOpenPrefs={openPrefs} />
        <main id="main" className="mx-auto w-full max-w-[1280px] flex-1 px-4 pb-28 pt-6 sm:px-6 lg:px-8 lg:pb-10">{page}</main>
        <footer className="border-t border-cream-200 px-4 py-6 pb-24 text-center text-xs text-ink-400 lg:pb-6">
          TrueBasket · Product data © Open Food Facts contributors (ODbL) · Prices from Open Prices and the stores you check · Not medical or dietary advice.
        </footer>
      </div>
      <MobileTabBar path={path} onOpenPrefs={openPrefs} />
      <PreferencesDialog open={prefsOpen} onClose={() => setPrefsOpen(false)} />
    </div>
  );
}

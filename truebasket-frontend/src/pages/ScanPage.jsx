import { Lightbulb, Ruler, Sun, ZoomIn } from "lucide-react";
import UploadCard from "../components/UploadCard.jsx";
import { LeafSprig, Script } from "../components/art.jsx";

const TIPS = [
  { icon: ZoomIn, text: "Fill about a third of the photo with the barcode." },
  { icon: Sun, text: "Good light, no glare across the stripes." },
  { icon: Ruler, text: "Hold the phone flat to the pack, 15–20 cm away." },
  { icon: Lightbulb, text: "Blurry? Tap the screen to focus before taking the photo." },
];

export default function ScanPage() {
  return (
    <div className="mx-auto grid max-w-5xl gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
      <section className="card p-5 sm:p-7" aria-labelledby="scan-heading">
        <p className="eyebrow mb-2">Scan & upload</p>
        <h1 id="scan-heading" className="font-display text-3xl font-semibold tracking-tight sm:text-4xl">What’s in your basket today?</h1>
        <p className="mt-2 text-ink-500">Scan the barcode live, take a photo, or choose one from your gallery or computer.</p>
        <div className="mt-6"><UploadCard /></div>
      </section>
      <aside className="space-y-4">
        <div className="card p-5">
          <h2 className="text-sm font-bold">For a quick, accurate read</h2>
          <ul className="mt-3 space-y-3 text-sm text-ink-700">
            {TIPS.map(({ icon: Icon, text }) => (
              <li key={text} className="flex gap-3"><span className="grid size-8 shrink-0 place-items-center rounded-xl bg-teal-50 text-teal-700"><Icon className="size-4" aria-hidden="true" /></span>{text}</li>
            ))}
          </ul>
        </div>
        <div className="relative overflow-hidden rounded-[var(--radius-card)] bg-teal-800 p-6 text-cream-50">
          <LeafSprig className="absolute -bottom-6 -right-6 h-36" tone="dark" />
          <Script className="relative text-[1.9rem]">Small choices,<br />big change.</Script>
        </div>
      </aside>
    </div>
  );
}

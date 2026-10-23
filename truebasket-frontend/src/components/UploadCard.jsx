import { useRef, useState } from "react";
import { AlertCircle, Barcode, Camera, Images, Loader2, ScanBarcode, Sparkles, UploadCloud, X } from "lucide-react";
import CameraScanner from "./CameraScanner.jsx";
import { Notice } from "./ui.jsx";
import { useBarcodeScan } from "../hooks/useBarcodeScan.js";
import { useObjectUrl } from "../hooks/useObjectUrl.js";
import { navigate } from "../lib/router.js";
import { analyzeProduct, labelReaderEnabled } from "../services/api.js";
import { getProduct, isBarcode } from "../services/openFoodFacts.js";

const ACCEPT = "image/*,.heic,.heif";

function Option({ icon: Icon, label, sub, onClick, testid }) {
  return (
    <button type="button" onClick={onClick} data-testid={testid}
      className="group flex flex-col items-center gap-2 rounded-2xl border border-cream-200 bg-white px-2 py-3 text-center transition-colors hover:border-teal-200 hover:bg-teal-50">
      <span className="grid size-11 place-items-center rounded-full bg-cream-100 text-teal-700 transition-colors group-hover:bg-white"><Icon className="size-5" aria-hidden="true" /></span>
      <span className="text-[13px] font-semibold leading-tight text-ink-900">{label}</span>
      {sub && <span className="-mt-1 text-[11px] leading-tight text-ink-500">{sub}</span>}
    </button>
  );
}

/** Upload a product photo: live camera, take a photo, gallery/files, drag & drop, or type the barcode. */
export default function UploadCard({ compact = false }) {
  const scan = useBarcodeScan();
  const preview = useObjectUrl(scan.file);
  const galleryRef = useRef(null);
  const cameraRef = useRef(null);
  const [camera, setCamera] = useState(false);
  const [drag, setDrag] = useState(false);
  const [manual, setManual] = useState("");
  const [gemma, setGemma] = useState({ busy: false, error: null });
  const busy = scan.status === "reading" || gemma.busy;

  const onInput = (e) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f) scan.scanFile(f);
  };

  const readWithGemma = async () => {
    setGemma({ busy: true, error: null });
    try {
      const res = await analyzeProduct({ image: scan.file });
      const p = res?.original_product || res?.product || res;
      const code = p?.barcode || p?.code;
      const q = [p?.brand, p?.product_name || p?.name].filter(Boolean).join(" ");
      if (code && isBarcode(code)) {
        try {
          await getProduct(code);
          return navigate(`/product/${code}`);
        } catch {
          if (q) return navigate("/search", { q });
        }
      }
      if (q) return navigate("/search", { q });
      throw new Error("The label was read, but no product name or barcode could be identified.");
    } catch (e) {
      setGemma({ busy: false, error: e.message });
    }
  };

  return (
    <div>
      <input ref={galleryRef} type="file" accept={ACCEPT} className="sr-only" onChange={onInput} data-testid="file-input" aria-label="Choose a product photo" tabIndex={-1} />
      <input ref={cameraRef} type="file" accept="image/*" capture="environment" className="sr-only" onChange={onInput} aria-label="Take a product photo" tabIndex={-1} />

      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) scan.scanFile(f); }}
        className={`relative rounded-2xl border-2 border-dashed p-5 text-center transition-colors ${drag ? "border-teal-500 bg-teal-50" : "border-cream-300 bg-cream-50/70"}`}
      >
        {scan.file && preview ? (
          <div className="flex flex-col items-center gap-3 sm:flex-row sm:text-left">
            <img src={preview} alt="Your product photo" className="h-40 w-full rounded-xl bg-white object-contain sm:size-32" />
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold">{scan.file.name || "Photo"}</p>
              {busy ? (
                <p className="mt-1 flex items-center justify-center gap-2 text-sm text-ink-700 sm:justify-start" role="status"><Loader2 className="size-4 animate-spin" aria-hidden="true" /> {gemma.busy ? "Reading the label with Gemma 4…" : scan.step}</p>
              ) : (
                <button type="button" className="btn-ghost mt-1 px-2 py-1 text-sm" onClick={scan.reset}><X className="size-4" aria-hidden="true" /> Remove photo</button>
              )}
            </div>
          </div>
        ) : (
          <button type="button" onClick={() => galleryRef.current?.click()} className="flex w-full flex-col items-center rounded-xl py-3">
            <span className="grid size-14 place-items-center rounded-2xl bg-white text-teal-700 shadow-card"><UploadCloud className="size-7" aria-hidden="true" /></span>
            <span className="mt-3 font-display text-lg font-semibold">Upload product image</span>
            <span className="mt-0.5 text-sm text-ink-500">Drag & drop, or tap to choose · JPG, PNG, WebP, HEIC</span>
          </button>
        )}
      </div>

      <div className={`mt-4 grid gap-2 ${compact ? "grid-cols-3" : "grid-cols-3"}`}>
        <Option icon={ScanBarcode} label="Scan barcode" sub="Live camera" onClick={() => setCamera(true)} testid="opt-live" />
        <Option icon={Camera} label="Take photo" sub="Camera" onClick={() => cameraRef.current?.click()} testid="opt-camera" />
        <Option icon={Images} label="Choose photo" sub="Gallery or files" onClick={() => galleryRef.current?.click()} testid="opt-gallery" />
      </div>

      {(scan.status === "invalid" || scan.status === "unreadable") && (
        <p role="alert" className="mt-3 flex items-start gap-2 text-sm font-medium text-clay-700"><AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />{scan.message}</p>
      )}

      {scan.status === "notfound" && !busy && (
        <div className="mt-4 space-y-3 text-left">
          <Notice tone="amber" icon={Barcode} title="We couldn’t read a barcode in this photo">
            Retake it with the barcode filling about a third of the photo, flat, sharp and well lit — or search by the product name below.
          </Notice>
          {labelReaderEnabled && (
            <button type="button" className="btn-secondary w-full" onClick={readWithGemma}><Sparkles className="size-4" aria-hidden="true" /> Read the label with Gemma 4 instead</button>
          )}
          {gemma.error && <p role="alert" className="text-sm text-clay-700">{gemma.error}</p>}
        </div>
      )}

      <form className="mt-4" onSubmit={(e) => {
        e.preventDefault();
        const t = manual.trim();
        if (!t) return;
        if (isBarcode(t)) navigate(`/product/${t.replace(/\s/g, "")}`);
        else navigate("/search", { q: t });
      }}>
        <label htmlFor={`manual-${compact ? "c" : "f"}`} className="mb-1.5 block text-sm font-semibold text-ink-700">No barcode? Search by product name</label>
        <div className="flex gap-2">
          <input id={`manual-${compact ? "c" : "f"}`} value={manual} maxLength={80} onChange={(e) => setManual(e.target.value)} enterKeyHint="search"
            placeholder="e.g. Kellogg’s muesli 500 g — or a barcode number" className="field-input" />
          <button type="submit" className="btn-primary shrink-0" disabled={!manual.trim()}>Find</button>
        </div>
        <p className="mt-1.5 text-xs text-ink-500">Results show every pack size, with filters for weight and brand.</p>
      </form>

      {camera && <CameraScanner onClose={() => setCamera(false)} onDetected={(code) => { setCamera(false); navigate(`/product/${code}`, { via: "camera" }); }} />}
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { CameraOff, Loader2, X } from "lucide-react";
import { decodeEanFromGray } from "../lib/barcodeDecoder.js";

/**
 * Live camera barcode scanner. Reads frames a few times per second with the
 * browser's BarcodeDetector when available, otherwise the built-in decoder.
 * Needs HTTPS or localhost (browser rule for camera access).
 */
export default function CameraScanner({ onDetected, onClose }) {
  const videoRef = useRef(null);
  const onDetectedRef = useRef(onDetected);
  onDetectedRef.current = onDetected;
  const [state, setState] = useState("starting"); // starting | scanning | error
  const [error, setError] = useState(null);

  useEffect(() => {
    let stream;
    let timer;
    let stopped = false;
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    let detector = null;

    const start = async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError(window.isSecureContext ? "This browser doesn’t support camera access." : "Camera access needs a secure (https://) page. Use Take photo instead.");
        setState("error");
        return;
      }
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false });
      } catch (e) {
        setError(e?.name === "NotAllowedError" ? "Camera permission was blocked. Allow it in your browser’s site settings, or use Take photo." : "No camera could be opened on this device.");
        setState("error");
        return;
      }
      if (stopped) return stream.getTracks().forEach((t) => t.stop());
      const v = videoRef.current;
      v.srcObject = stream;
      await v.play().catch(() => {});
      try {
        if ("BarcodeDetector" in window) {
          const sup = await window.BarcodeDetector.getSupportedFormats();
          const f = ["ean_13", "ean_8", "upc_a", "upc_e"].filter((x) => sup.includes(x));
          if (f.length) detector = new window.BarcodeDetector({ formats: f });
        }
      } catch {
        detector = null;
      }
      setState("scanning");

      const votes = new Map();
      const tick = async () => {
        if (stopped || !v.videoWidth) return;
        let code = null;
        if (detector) {
          try {
            const r = await detector.detect(v);
            code = r.map((c) => c.rawValue).find((x) => /^\d{8,14}$/.test(x)) || null;
          } catch {
            code = null;
          }
        }
        if (!code) {
          // Centre band of the frame, downscaled — where the guide box is.
          const sw = v.videoWidth;
          const sh = v.videoHeight;
          const cw = Math.min(1100, sw);
          const ch = Math.round((cw / sw) * sh * 0.6);
          canvas.width = cw;
          canvas.height = ch;
          ctx.drawImage(v, 0, sh * 0.2, sw, sh * 0.6, 0, 0, cw, ch);
          const { data } = ctx.getImageData(0, 0, cw, ch);
          const gray = new Uint8ClampedArray(cw * ch);
          for (let i = 0, j = 0; i < gray.length; i++, j += 4) gray[i] = (data[j] * 77 + data[j + 1] * 150 + data[j + 2] * 29) >> 8;
          const c = decodeEanFromGray(gray, cw, ch, { lines: 28 });
          if (c) {
            // Require the same code in two frames to avoid misreads.
            votes.set(c, (votes.get(c) || 0) + 1);
            if (votes.get(c) >= 2) code = c;
          }
        }
        if (code && !stopped) {
          stopped = true;
          navigator.vibrate?.(60);
          onDetectedRef.current(code);
          return;
        }
        timer = setTimeout(tick, 220);
      };
      tick();
    };
    start();
    return () => {
      stopped = true;
      clearTimeout(timer);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ink-900/95 text-cream-50" role="dialog" aria-modal="true" aria-label="Scan barcode with camera">
      <div className="flex items-center justify-between px-4 py-3">
        <p className="font-semibold">Scan barcode</p>
        <button type="button" onClick={onClose} className="grid size-10 place-items-center rounded-full hover:bg-white/10" aria-label="Close camera">
          <X className="size-5" />
        </button>
      </div>
      <div className="relative mx-auto flex w-full max-w-3xl flex-1 items-center justify-center overflow-hidden">
        <video ref={videoRef} playsInline muted className="max-h-full w-full object-contain" />
        {state === "scanning" && (
          <div className="pointer-events-none absolute inset-x-[10%] top-1/2 h-[34%] -translate-y-1/2 rounded-2xl border-2 border-amber-400 shadow-[0_0_0_9999px_rgb(0_0_0/0.35)]">
            <div className="absolute inset-x-4 top-1/2 h-0.5 animate-pulse bg-amber-400/80" />
          </div>
        )}
        {state === "starting" && <p className="absolute flex items-center gap-2"><Loader2 className="size-5 animate-spin" /> Opening camera…</p>}
        {state === "error" && (
          <div className="absolute mx-6 max-w-sm rounded-2xl bg-white p-6 text-center text-ink-900">
            <CameraOff className="mx-auto size-8 text-clay-700" aria-hidden="true" />
            <p className="mt-3 font-semibold">Camera unavailable</p>
            <p className="mt-1 text-sm text-ink-500">{error}</p>
            <button type="button" className="btn-primary mt-4" onClick={onClose}>OK</button>
          </div>
        )}
      </div>
      <p className="px-6 py-5 text-center text-sm text-cream-200">Hold the barcode inside the box, about 15–20 cm away, in good light.</p>
    </div>
  );
}

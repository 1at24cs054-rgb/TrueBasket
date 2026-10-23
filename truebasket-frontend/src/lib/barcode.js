/**
 * Reads a grocery barcode (EAN-13, EAN-8, UPC-A/E) from a photo.
 *
 * Tries, in order, stopping at the first success:
 *  1. The browser's BarcodeDetector (Chrome on Android/macOS/ChromeOS, recent Safari).
 *  2. TrueBasket's built-in EAN/UPC decoder at several image sizes.
 *  3. ZXing (@zxing/library), loaded only when needed.
 *  4. The built-in decoder on rotated copies (for tilted photos).
 *
 * Returns { code, method } or { code: null, reason }.
 */
import { decodeEanFromGray } from "./barcodeDecoder.js";

const isCode = (v) => typeof v === "string" && /^\d{8,14}$/.test(v);

async function loadBitmap(file) {
  if (typeof createImageBitmap === "function") {
    try {
      return await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch {
      /* fall back to <img> */
    }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Draws the image scaled (and optionally rotated) and returns luminance values. */
function grayAt(source, maxSide, angleDeg = 0) {
  const sw = source.width;
  const sh = source.height;
  const scale = Math.min(1, maxSide / Math.max(sw, sh));
  const w = Math.max(1, Math.round(sw * scale));
  const h = Math.max(1, Math.round(sh * scale));
  const rad = (angleDeg * Math.PI) / 180;
  const cw = Math.round(Math.abs(w * Math.cos(rad)) + Math.abs(h * Math.sin(rad)));
  const ch = Math.round(Math.abs(w * Math.sin(rad)) + Math.abs(h * Math.cos(rad)));
  const canvas = document.createElement("canvas");
  canvas.width = cw;
  canvas.height = ch;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, cw, ch);
  ctx.translate(cw / 2, ch / 2);
  ctx.rotate(rad);
  ctx.drawImage(source, -w / 2, -h / 2, w, h);
  const { data } = ctx.getImageData(0, 0, cw, ch);
  const gray = new Uint8ClampedArray(cw * ch);
  for (let i = 0, j = 0; i < gray.length; i++, j += 4) {
    gray[i] = (data[j] * 77 + data[j + 1] * 150 + data[j + 2] * 29) >> 8;
  }
  return { gray, width: cw, height: ch };
}

async function tryNative(source) {
  if (typeof window === "undefined" || !("BarcodeDetector" in window)) return null;
  try {
    const supported = (await window.BarcodeDetector.getSupportedFormats?.()) || [];
    const formats = ["ean_13", "ean_8", "upc_a", "upc_e"].filter((f) => supported.includes(f));
    if (formats.length === 0) return null;
    const detector = new window.BarcodeDetector({ formats });
    const codes = await detector.detect(source);
    return codes.map((c) => c.rawValue).find(isCode) || null;
  } catch {
    return null;
  }
}

async function tryZxing(gray, width, height) {
  try {
    const zx = await import("@zxing/library");
    const hints = new Map();
    hints.set(zx.DecodeHintType.POSSIBLE_FORMATS, [zx.BarcodeFormat.EAN_13, zx.BarcodeFormat.EAN_8, zx.BarcodeFormat.UPC_A, zx.BarcodeFormat.UPC_E]);
    hints.set(zx.DecodeHintType.TRY_HARDER, true);
    const reader = new zx.MultiFormatReader();
    reader.setHints(hints);
    const source = new zx.RGBLuminanceSource(gray, width, height);
    const result = reader.decode(new zx.BinaryBitmap(new zx.HybridBinarizer(source)));
    const text = result?.getText?.();
    if (!isCode(text)) return null;
    return text.length === 12 ? `0${text}` : text; // UPC-A → EAN-13
  } catch {
    return null; // not found, or library unavailable
  }
}

const nextFrame = () => new Promise((r) => setTimeout(r, 0));

export async function readBarcode(file, { onStep } = {}) {
  let source;
  try {
    source = await loadBitmap(file);
  } catch {
    return { code: null, reason: "unreadable" };
  }

  const native = await tryNative(source);
  if (native) return { code: native, method: "browser" };

  onStep?.("Decoding the barcode…");
  const maxSide = Math.max(source.width, source.height);
  const sizes = [1600, 1000, Math.min(maxSide, 3200)].filter((s, i, a) => a.indexOf(s) === i);
  for (const size of sizes) {
    await nextFrame(); // keep the page responsive
    const { gray, width, height } = grayAt(source, size);
    const code = decodeEanFromGray(gray, width, height);
    if (code) return { code, method: "built-in" };
  }

  onStep?.("Trying a deeper scan…");
  await nextFrame();
  const mid = grayAt(source, 1600);
  const zx = await tryZxing(mid.gray, mid.width, mid.height);
  if (zx) return { code: zx, method: "zxing" };

  for (const angle of [22, -22, 45, -45]) {
    await nextFrame();
    const { gray, width, height } = grayAt(source, 1200, angle);
    const code = decodeEanFromGray(gray, width, height);
    if (code) return { code, method: "built-in (rotated)" };
  }

  source.close?.();
  return { code: null, reason: "not_found" };
}

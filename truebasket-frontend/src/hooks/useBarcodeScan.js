import { useCallback, useState } from "react";
import { readBarcode } from "../lib/barcode.js";
import { navigate } from "../lib/router.js";

export const ACCEPTED = ["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"];
export const MAX_BYTES = 20 * 1024 * 1024;

export function validatePhoto(file) {
  if (!file) return "No file selected.";
  const heicByName = /\.(heic|heif)$/i.test(file.name || "");
  if (file.type && !ACCEPTED.includes(file.type) && !heicByName && !file.type.startsWith("image/")) {
    return `“${file.name}” isn’t an image. Choose a JPG, PNG, WebP or HEIC photo.`;
  }
  if (file.size > MAX_BYTES) return `That photo is larger than 20 MB. Choose a smaller one.`;
  return null;
}

/**
 * Shared photo → product flow used by the home page and the Scan page.
 * On success it opens the product page; otherwise it explains what happened.
 */
export function useBarcodeScan() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | reading | notfound | unreadable | invalid
  const [step, setStep] = useState("");
  const [message, setMessage] = useState(null);

  const scanFile = useCallback(async (f) => {
    setMessage(null);
    if (!f) {
      setFile(null);
      setStatus("idle");
      return;
    }
    const problem = validatePhoto(f);
    if (problem) {
      setStatus("invalid");
      setMessage(problem);
      return;
    }
    setFile(f);
    setStatus("reading");
    setStep("Looking for a barcode…");
    const res = await readBarcode(f, { onStep: setStep });
    if (res.code) {
      navigate(`/product/${res.code}`, { via: "photo" });
      return;
    }
    if (res.reason === "unreadable") {
      setStatus("unreadable");
      setMessage(
        /\.(heic|heif)$/i.test(f.name || "") || /heic|heif/.test(f.type)
          ? "This browser can’t open HEIC photos. On iPhone, choose “Most Compatible” in Settings → Camera → Formats, or use Take photo."
          : "This image couldn’t be opened. Try another photo."
      );
      return;
    }
    setStatus("notfound");
  }, []);

  const reset = useCallback(() => {
    setFile(null);
    setStatus("idle");
    setMessage(null);
  }, []);

  return { file, status, step, message, scanFile, reset };
}

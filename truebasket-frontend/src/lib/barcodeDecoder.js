/**
 * Built-in EAN-13 / EAN-8 / UPC-A decoder for grocery barcodes.
 *
 * Works on a grayscale image (Uint8 array, width, height). Scans many lines
 * horizontally and vertically, in both directions, binarises each line with
 * an adaptive threshold, decodes bar widths and validates the check digit.
 * A code is accepted only when at least two scan lines agree.
 *
 * Pure JavaScript, no dependencies — used when the browser has no built-in
 * BarcodeDetector (Windows/Linux Chrome, Firefox, older Safari).
 */

// Widths (in modules) of the 4 runs for each digit. L and R share widths; G is L reversed.
const L = ["3211", "2221", "2122", "1411", "1132", "1231", "1114", "1312", "1213", "3112"].map((s) => [...s].map(Number));
const G = L.map((p) => [...p].reverse());
// Parity pattern of the 6 left digits (0 = L, 1 = G) encodes the first EAN-13 digit.
const PARITY = ["000000", "001011", "001101", "001110", "010011", "011001", "011100", "010101", "010110", "011010"];

const MAX_DIGIT_ERR = 1.6;

function matchDigit(runs, start, tables) {
  const w = runs[start] + runs[start + 1] + runs[start + 2] + runs[start + 3];
  if (!w) return null;
  let best = null;
  for (let t = 0; t < tables.length; t++) {
    const table = tables[t];
    for (let d = 0; d < 10; d++) {
      const p = table[d];
      let err = 0;
      for (let k = 0; k < 4; k++) err += Math.abs((runs[start + k] * 7) / w - p[k]);
      if (!best || err < best.err) best = { d, t, err };
    }
  }
  return best && best.err <= MAX_DIGIT_ERR ? best : null;
}

/** Guard of n runs (bar/space alternating) whose widths are each close to `unit`. */
function isGuard(runs, start, n, unit) {
  if (start + n > runs.length) return false;
  for (let k = 0; k < n; k++) {
    const r = runs[start + k] / unit;
    if (r < 0.4 || r > 2.2) return false;
  }
  return true;
}

function checksumOk(digits) {
  const n = digits.length;
  let sum = 0;
  for (let i = 0; i < n - 1; i++) {
    const fromRight = n - 1 - i; // position from the check digit
    sum += digits[i] * (fromRight % 2 === 1 ? 3 : 1);
  }
  return (10 - (sum % 10)) % 10 === digits[n - 1];
}

/**
 * `runs` alternate starting with a BAR at index i (the first bar of the start guard).
 * Returns a code string or null.
 */
function tryEan13(runs, i) {
  if (i + 59 > runs.length) return null;
  const unit = (runs[i] + runs[i + 1] + runs[i + 2]) / 3;
  // Quiet zone before the start guard should be clearly wider than a module.
  if (i > 0 && runs[i - 1] < unit * 2.5) return null;
  if (!isGuard(runs, i, 3, unit)) return null;
  let p = i + 3;
  const left = [];
  let parity = "";
  for (let k = 0; k < 6; k++, p += 4) {
    const m = matchDigit(runs, p, [L, G]);
    if (!m) return null;
    left.push(m.d);
    parity += m.t;
  }
  const sideUnit = (runs.slice(i + 3, p).reduce((a, b) => a + b, 0)) / 42;
  if (!isGuard(runs, p, 5, sideUnit)) return null;
  p += 5;
  const right = [];
  for (let k = 0; k < 6; k++, p += 4) {
    const m = matchDigit(runs, p, [L]); // R widths == L widths
    if (!m) return null;
    right.push(m.d);
  }
  if (!isGuard(runs, p, 3, sideUnit)) return null;
  const first = PARITY.indexOf(parity);
  if (first < 0) return null;
  const digits = [first, ...left, ...right];
  return checksumOk(digits) ? digits.join("") : null;
}

function tryEan8(runs, i) {
  if (i + 43 > runs.length) return null;
  const unit = (runs[i] + runs[i + 1] + runs[i + 2]) / 3;
  if (i > 0 && runs[i - 1] < unit * 2.5) return null;
  if (!isGuard(runs, i, 3, unit)) return null;
  let p = i + 3;
  const digits = [];
  for (let k = 0; k < 4; k++, p += 4) {
    const m = matchDigit(runs, p, [L]);
    if (!m || m.t !== 0) return null;
    digits.push(m.d);
  }
  const sideUnit = runs.slice(i + 3, p).reduce((a, b) => a + b, 0) / 28;
  if (!isGuard(runs, p, 5, sideUnit)) return null;
  p += 5;
  for (let k = 0; k < 4; k++, p += 4) {
    const m = matchDigit(runs, p, [L]);
    if (!m) return null;
    digits.push(m.d);
  }
  if (!isGuard(runs, p, 3, sideUnit)) return null;
  return checksumOk(digits) ? digits.join("") : null;
}

/** Binarises one line (already averaged) and returns run lengths starting with a dark run. */
function lineToRuns(line, n, winDiv = 16) {
  // Integral for a moving-average adaptive threshold.
  const win = Math.max(8, Math.round(n / winDiv));
  const integ = new Float64Array(n + 1);
  for (let x = 0; x < n; x++) integ[x + 1] = integ[x] + line[x];
  let lo = 255;
  let hi = 0;
  for (let x = 0; x < n; x++) {
    if (line[x] < lo) lo = line[x];
    if (line[x] > hi) hi = line[x];
  }
  if (hi - lo < 40) return null; // no contrast on this line
  const minContrast = (hi - lo) * 0.08;
  const runs = [];
  let cur = -1;
  let len = 0;
  for (let x = 0; x < n; x++) {
    const a = Math.max(0, x - win);
    const b = Math.min(n, x + win + 1);
    const mean = (integ[b] - integ[a]) / (b - a);
    // Flat regions (no local contrast) count as light, so quiet zones stay quiet.
    const dark = line[x] < mean - minContrast * 0.25 ? 1 : 0;
    if (dark === cur) len++;
    else {
      if (cur !== -1) runs.push({ dark: cur, len });
      cur = dark;
      len = 1;
    }
  }
  runs.push({ dark: cur, len });
  return runs;
}

function decodeRuns(runObjs, found) {
  for (const dirRuns of [runObjs, [...runObjs].reverse()]) {
    const widths = dirRuns.map((r) => r.len);
    for (let i = 0; i < dirRuns.length; i++) {
      if (!dirRuns[i].dark) continue;
      const code = tryEan13(widths, i) || tryEan8(widths, i);
      if (code) {
        found.set(code, (found.get(code) || 0) + 1);
        i += 20;
      }
    }
  }
}

/**
 * @param {Uint8Array|Uint8ClampedArray} gray  luminance, row-major
 * @returns {string|null} EAN-13 / EAN-8 code (UPC-A returned as 13 digits with leading 0)
 */
export function decodeEanFromGray(gray, width, height, { lines = 48 } = {}) {
  const found = new Map();
  const scan = (isRow) => {
    const len = isRow ? width : height;
    const across = isRow ? height : width;
    const line = new Float32Array(len);
    const sharp = new Float32Array(len);
    for (let s = 1; s <= lines; s++) {
      const c = Math.round((across * s) / (lines + 1));
      line.fill(0);
      let count = 0;
      for (let o = -1; o <= 1; o++) {
        const cc = c + o;
        if (cc < 0 || cc >= across) continue;
        count++;
        if (isRow) for (let x = 0; x < len; x++) line[x] += gray[cc * width + x];
        else for (let y = 0; y < len; y++) line[y] += gray[y * width + cc];
      }
      for (let x = 0; x < len; x++) line[x] /= count;
      const before = found.size;
      const runs = lineToRuns(line, len);
      if (runs) decodeRuns(runs, found);
      if (found.size === before) {
        // Retry with a sharpened line (helps blurry photos) and a tighter threshold window.
        for (let x = 1; x < len - 1; x++) sharp[x] = Math.max(0, Math.min(255, (line[x] * 4 - line[x - 1] - line[x + 1]) / 2));
        sharp[0] = line[0];
        sharp[len - 1] = line[len - 1];
        for (const div of [16, 40]) {
          const r2 = lineToRuns(sharp, len, div);
          if (r2) decodeRuns(r2, found);
        }
      }
    }
  };
  scan(true);
  scan(false);
  if (found.size === 0) return null;
  const [code, votes] = [...found.entries()].sort((a, b) => b[1] - a[1])[0];
  return votes >= 2 ? code : null;
}

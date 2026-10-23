/** Decorative illustrations (pure SVG, no photos). All are aria-hidden. */

export function LeafSprig({ className = "", tone = "light" }) {
  const c = tone === "light" ? ["#3f7d5c", "#5f9c6f", "#2f6a4f"] : ["#a9d2ca", "#d5e9e5", "#7fb8ad"];
  return (
    <svg viewBox="0 0 120 160" className={className} aria-hidden="true" fill="none">
      <path d="M60 158C58 120 60 80 72 30" stroke={c[2]} strokeWidth="3" strokeLinecap="round" />
      <path d="M70 40c-22-6-36-24-34-38 16 2 32 16 34 38Z" fill={c[0]} />
      <path d="M72 38c18-12 36-12 44-4-10 12-28 14-44 4Z" fill={c[1]} />
      <path d="M64 82c-24-2-42-18-44-34 18 0 38 14 44 34Z" fill={c[1]} />
      <path d="M66 78c20-14 40-14 48-6-10 14-30 16-48 6Z" fill={c[0]} />
      <path d="M61 122c-20 2-38-10-42-24 16-2 34 8 42 24Z" fill={c[0]} />
      <path d="M62 118c16-12 34-14 42-8-8 12-26 16-42 8Z" fill={c[1]} />
    </svg>
  );
}

export function Logo({ light = false }) {
  return (
    <span className="flex items-center gap-2.5">
      <svg viewBox="0 0 40 40" className="size-9 shrink-0" aria-hidden="true">
        <path d="M20 37C11 33 6 24 8 12c9 1 15 8 12 25Z" fill={light ? "#7fb8ad" : "#2f6a4f"} />
        <path d="M20 37c9-4 14-13 12-25-9 1-15 8-12 25Z" fill={light ? "#d5e9e5" : "#5f9c6f"} />
        <path d="M20 36V18" stroke={light ? "#0b3b37" : "#f7f2e8"} strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      <span className="leading-none">
        <span className={`block font-display text-[1.6rem] font-semibold tracking-tight ${light ? "text-cream-50" : "text-teal-800"}`}>TrueBasket</span>
        <span className={`mt-1 block text-[9px] font-bold uppercase tracking-[0.22em] ${light ? "text-teal-100" : "text-teal-600"}`}>Know what goes inside</span>
      </span>
    </span>
  );
}

/** Illustrated grocery bag with produce for the hero. */
export function BasketIllustration({ className = "" }) {
  return (
    <svg viewBox="0 0 360 260" className={className} aria-hidden="true">
      <ellipse cx="185" cy="244" rx="150" ry="12" fill="#0b3b37" opacity="0.35" />
      {/* greens */}
      <path d="M118 92c-30-40-10-78 10-86 8 30 4 64-10 86Z" fill="#5f9c6f" />
      <path d="M128 96c-6-46 22-74 44-74-4 32-20 60-44 74Z" fill="#3f7d5c" />
      <path d="M232 90c10-44 46-60 66-52-14 28-38 48-66 52Z" fill="#5f9c6f" />
      {/* baguette */}
      <rect x="196" y="18" width="26" height="110" rx="13" transform="rotate(18 209 73)" fill="#d9a35b" />
      <path d="M206 40l14 6M202 60l14 6M198 80l14 6" stroke="#b07a35" strokeWidth="3" strokeLinecap="round" transform="rotate(18 209 73)" />
      {/* tomato, lemon, carrot */}
      <circle cx="96" cy="200" r="30" fill="#d9573b" />
      <path d="M86 172c6 4 14 4 20 0" stroke="#3f7d5c" strokeWidth="4" strokeLinecap="round" />
      <ellipse cx="290" cy="212" rx="30" ry="24" fill="#f2c84b" />
      <path d="M300 80l-34 120" stroke="#e98a3a" strokeWidth="16" strokeLinecap="round" />
      <path d="M302 78c4-12 14-18 22-16M300 78c-6-12-2-22 4-26" stroke="#5f9c6f" strokeWidth="4" strokeLinecap="round" fill="none" />
      {/* bag */}
      <path d="M120 96h150l-12 150H132Z" fill="#efe2c6" />
      <path d="M120 96h150l-3 30H123Z" fill="#e3d1ab" />
      <path d="M160 96c0-34 70-34 70 0" stroke="#c9b48a" strokeWidth="7" fill="none" strokeLinecap="round" />
      <g transform="translate(160 156)">
        <path d="M18 36C9 32 5 23 7 12c9 1 14 8 11 24Z" fill="#2f6a4f" />
        <path d="M18 36c9-4 13-12 11-24-9 1-14 8-11 24Z" fill="#5f9c6f" />
        <text x="38" y="30" fontFamily="Fraunces, Georgia, serif" fontSize="19" fontWeight="600" fill="#0b3b37">TrueBasket</text>
      </g>
    </svg>
  );
}

export function Script({ children, className = "" }) {
  return <p className={`font-script leading-[1.05] ${className}`}>{children}</p>;
}

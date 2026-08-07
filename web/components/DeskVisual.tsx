/** Stylized desk visual — colors follow active theme tokens. */
export function DeskVisual() {
  return (
    <svg
      className="desk-visual"
      viewBox="0 0 520 460"
      role="img"
      aria-label="Desk with truth notes, a job description, and a draft letter"
    >
      <defs>
        <linearGradient id="deskWood" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.22" />
          <stop offset="100%" stopColor="var(--accent-deep)" stopOpacity="0.1" />
        </linearGradient>
        <linearGradient id="paperGlow" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--panel-solid)" />
          <stop offset="100%" stopColor="var(--mist)" />
        </linearGradient>
      </defs>

      {/* desk surface */}
      <rect x="24" y="280" width="472" height="150" rx="18" fill="url(#deskWood)" />
      <rect x="24" y="280" width="472" height="18" rx="9" fill="var(--accent)" opacity="0.28" />

      {/* truth vault card */}
      <g transform="translate(48 72) rotate(-6)">
        <rect
          width="168"
          height="210"
          rx="14"
          fill="url(#paperGlow)"
          stroke="var(--line)"
          strokeWidth="2"
        />
        <text x="18" y="36" fontFamily="Georgia, serif" fontSize="18" fill="var(--accent-deep)">
          Truth
        </text>
        <rect x="18" y="52" width="110" height="8" rx="4" fill="var(--accent)" opacity="0.4" />
        <rect x="18" y="72" width="132" height="6" rx="3" fill="var(--ink-soft)" opacity="0.28" />
        <rect x="18" y="90" width="120" height="6" rx="3" fill="var(--ink-soft)" opacity="0.22" />
        <rect x="18" y="108" width="128" height="6" rx="3" fill="var(--ink-soft)" opacity="0.2" />
        <rect x="18" y="126" width="96" height="6" rx="3" fill="var(--ink-soft)" opacity="0.18" />
        <rect x="18" y="156" width="54" height="22" rx="11" fill="var(--accent-bright)" opacity="0.85" />
        <rect x="80" y="156" width="54" height="22" rx="11" fill="var(--accent)" opacity="0.4" />
      </g>

      {/* JD sheet */}
      <g transform="translate(200 48) rotate(4)">
        <rect
          width="190"
          height="240"
          rx="14"
          fill="var(--panel-solid)"
          stroke="var(--line)"
          strokeWidth="2"
        />
        <text x="18" y="36" fontFamily="Georgia, serif" fontSize="16" fill="var(--ink)">
          Job description
        </text>
        <rect x="18" y="56" width="140" height="7" rx="3.5" fill="var(--ink)" opacity="0.55" />
        <rect x="18" y="78" width="154" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.28" />
        <rect x="18" y="94" width="148" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.24" />
        <rect x="18" y="110" width="150" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.2" />
        <rect x="18" y="126" width="132" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.18" />
        <rect x="18" y="142" width="146" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.16" />
        <rect x="18" y="168" width="100" height="5" rx="2.5" fill="var(--accent)" opacity="0.4" />
        <rect x="18" y="184" width="120" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.15" />
        <rect x="18" y="200" width="112" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.15" />
      </g>

      {/* draft letter */}
      <g transform="translate(330 110) rotate(-3)">
        <rect
          width="160"
          height="200"
          rx="14"
          fill="var(--panel-solid)"
          stroke="var(--accent-bright)"
          strokeWidth="2.5"
        />
        <text x="16" y="34" fontFamily="Georgia, serif" fontSize="15" fill="var(--accent-deep)">
          Draft
        </text>
        <rect x="16" y="52" width="48" height="14" rx="7" fill="var(--accent-bright)" opacity="0.8" />
        <rect x="16" y="82" width="118" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.3" />
        <rect x="16" y="98" width="124" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.24" />
        <rect x="16" y="114" width="110" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.22" />
        <rect x="16" y="130" width="120" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.2" />
        <rect x="16" y="146" width="96" height="5" rx="2.5" fill="var(--ink-soft)" opacity="0.18" />
        <text x="16" y="182" fontFamily="system-ui, sans-serif" fontSize="11" fill="var(--accent)">
          awaiting approve
        </text>
      </g>

      {/* spruce sprig accent */}
      <g transform="translate(420 24)" opacity="0.9">
        <path
          d="M18 8 C18 40 6 58 6 88"
          fill="none"
          stroke="var(--accent)"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <path d="M18 28 L2 40 M18 44 L34 52 M18 60 L4 72" stroke="var(--accent-bright)" strokeWidth="2.5" strokeLinecap="round" />
      </g>
    </svg>
  );
}

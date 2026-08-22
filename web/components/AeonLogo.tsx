/**
 * AEON OS brand mark — the stylized glowing "A" from the AEON reference
 * design: two overlapping angular A strokes with a crossbar and a small
 * apex triangle, rendered in the brand cyan gradient with a soft glow.
 *
 * Server-safe (no hooks) so it can be used in layouts, sidebars and pages.
 */
export default function AeonLogo({
  size = 32,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="AEON OS"
    >
      <defs>
        <linearGradient id="aeonLogoGrad" x1="0" y1="48" x2="48" y2="0">
          <stop offset="0%" stopColor="#00a8ff" />
          <stop offset="100%" stopColor="#00d2ff" />
        </linearGradient>
      </defs>

      {/* Offset back layer — outlined A (subtle depth) */}
      <g transform="translate(4, 2.5)" opacity="0.35">
        <path
          d="M13 41 L27 11 L41 41"
          stroke="url(#aeonLogoGrad)"
          strokeWidth="3.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M20 28 L34 28"
          stroke="url(#aeonLogoGrad)"
          strokeWidth="3.5"
          strokeLinecap="round"
        />
      </g>

      {/* Main A — angular strokes + crossbar */}
      <path
        d="M10 41 L24 11 L38 41"
        stroke="url(#aeonLogoGrad)"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M15 29 L33 29"
        stroke="url(#aeonLogoGrad)"
        strokeWidth="4.5"
        strokeLinecap="round"
      />

      {/* Apex accent triangle */}
      <path d="M24 3 L27.4 8.6 L20.6 8.6 Z" fill="url(#aeonLogoGrad)" />
    </svg>
  );
}

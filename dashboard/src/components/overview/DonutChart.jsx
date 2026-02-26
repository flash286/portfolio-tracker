import { useRef, useState } from "preact/hooks";
import { COLORS } from "../../utils";

export function DonutChart({ items, outerR = 90, innerR = 56, id = "donut" }) {
  const [tip, setTip] = useState(null);
  const containerRef = useRef(null);
  const total = items.reduce((s, i) => s + i.value, 0);
  if (total === 0) return null;

  const pad = 16;
  const size = (outerR + pad) * 2;
  const cx = size / 2, cy = size / 2;
  const gap = 0.03;

  let startAngle = -Math.PI / 2;
  const segments = items.map((item, i) => {
    const pct = item.value / total;
    const angle = pct * Math.PI * 2;
    const endAngle = startAngle + angle;
    const s = startAngle + gap / 2;
    const e = endAngle - gap / 2;
    startAngle = endAngle;
    if (e <= s) return null;

    const x1 = cx + outerR * Math.cos(s), y1 = cy + outerR * Math.sin(s);
    const x2 = cx + outerR * Math.cos(e), y2 = cy + outerR * Math.sin(e);
    const x3 = cx + innerR * Math.cos(e), y3 = cy + innerR * Math.sin(e);
    const x4 = cx + innerR * Math.cos(s), y4 = cy + innerR * Math.sin(s);
    const large = angle > Math.PI ? 1 : 0;
    const d = `M${x1},${y1} A${outerR},${outerR} 0 ${large},1 ${x2},${y2} L${x3},${y3} A${innerR},${innerR} 0 ${large},0 ${x4},${y4} Z`;
    const color = COLORS[i % COLORS.length];

    return { d, color, item, i };
  }).filter(Boolean);

  const handleMove = (e, item) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const clientX = e.clientX || e.touches?.[0]?.clientX || 0;
    const clientY = e.clientY || e.touches?.[0]?.clientY || 0;
    setTip({
      label: item.label,
      value: item.value.toFixed(1),
      x: clientX - rect.left + 14,
      y: clientY - rect.top - 36,
    });
  };

  return (
    <div class="chart-container" ref={containerRef} style="position:relative">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          {segments.map((seg) => (
            <linearGradient key={seg.i} id={`dg-${id}-${seg.i}`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color={seg.color} />
              <stop offset="100%" stop-color={seg.color} stop-opacity="0.7" />
            </linearGradient>
          ))}
        </defs>
        {segments.map((seg) => (
          <path
            key={seg.i}
            d={seg.d}
            fill={`url(#dg-${id}-${seg.i})`}
            style="cursor:pointer;transition:opacity 0.15s"
            onMouseEnter={(e) => handleMove(e, seg.item)}
            onMouseMove={(e) => handleMove(e, seg.item)}
            onMouseLeave={() => setTip(null)}
            onClick={(e) => (tip ? setTip(null) : handleMove(e, seg.item))}
          />
        ))}
        <text x={cx} y={cy - 6} fill="var(--text)" font-size="18" font-weight="700"
          text-anchor="middle" dominant-baseline="middle" font-family="'JetBrains Mono', monospace">
          {items.length}
        </text>
        <text x={cx} y={cy + 12} fill="var(--text3)" font-size="10" font-weight="500"
          text-anchor="middle" dominant-baseline="middle" letter-spacing="0.5">
          POSITIONS
        </text>
      </svg>

      {tip && (
        <div class="tooltip" style={{ opacity: 1, left: tip.x + "px", top: tip.y + "px" }}>
          <strong>{tip.label}</strong><br />{tip.value}%
        </div>
      )}

      <div class="legend">
        {items.map((item, i) => (
          <div key={i} class="legend-item">
            <span class="legend-pill" style={{ background: COLORS[i % COLORS.length] }} />
            <span class="legend-text">{item.name}</span>
            <span class="legend-value">{item.value.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

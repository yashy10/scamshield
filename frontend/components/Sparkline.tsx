/** A small trend line: the period in the de-emphasis hue, today's point in the accent. */
export function Sparkline({ values, width = 120, height = 32 }: { values: number[]; width?: number; height?: number }) {
  if (values.length < 2) return <div style={{ width, height }} />;
  const max = Math.max(...values, 1);
  const step = width / (values.length - 1);
  const y = (v: number) => height - 3 - (v / max) * (height - 6);
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${y(v).toFixed(1)}`);
  const last = values[values.length - 1];
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden className="overflow-visible">
      <path
        d={`M0,${height} L${points.join(" L")} L${width},${height} Z`}
        fill="color-mix(in oklab, var(--color-accent) 10%, transparent)"
      />
      <polyline points={points.join(" ")} fill="none" stroke="var(--color-muted)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={width} cy={y(last)} r={4} fill="var(--color-accent)" stroke="var(--color-surface)" strokeWidth={2} />
    </svg>
  );
}

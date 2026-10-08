// Change vs. the previous period. Hidden when there's nothing to compare against.
export default function Delta({ cur, prev }) {
  if (!prev) return null;
  const pct = ((cur - prev) / prev) * 100;
  if (!isFinite(pct) || Math.abs(pct) < 0.5) return <span className="kpi-delta neutral">= período anterior</span>;
  const pos = pct >= 0;
  return (
    <span className={`kpi-delta ${pos ? "pos" : "neg"}`}>
      {pos ? "▲" : "▼"} {Math.abs(pct).toFixed(0)}%
    </span>
  );
}

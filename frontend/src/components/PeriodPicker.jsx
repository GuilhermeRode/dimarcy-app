import { useState } from "react";
import { addDays, localDate } from "../format";

const PRESETS = [
  { key: "7d", label: "7 dias", start: () => addDays(localDate(), -6), end: localDate },
  { key: "month", label: "Este mês", start: () => `${localDate().slice(0, 8)}01`, end: localDate },
  { key: "year", label: "Este ano", start: () => `${new Date().getFullYear()}-01-01`, end: localDate },
];

export const defaultPeriod = () => ({ start: PRESETS[2].start(), end: localDate() });

// The active chip comes from `value` (so a parent can set the period too), except "Personalizado", which is a mode.
export default function PeriodPicker({ value, onChange, presets = PRESETS, label }) {
  const [custom, setCustom] = useState(false);
  const match = presets.find((p) => p.start() === value.start && p.end() === value.end);
  const active = custom || !match ? "custom" : match.key;
  return (
    <div className="period-block">
      <div className="period-row">
        {label && <span className="period-label">{label}</span>}
        <div className="seg-control" role="group" aria-label={label || "Período"}>
          {presets.map((p) => (
            <button key={p.key} type="button" className={active === p.key ? "on" : ""} aria-pressed={active === p.key}
              onClick={() => { setCustom(false); onChange({ start: p.start(), end: p.end() }); }}>
              {p.label}
            </button>
          ))}
          <button type="button" className={active === "custom" ? "on" : ""} aria-pressed={active === "custom"}
            onClick={() => setCustom(true)}>Personalizado</button>
        </div>
      </div>
      {active === "custom" && (
        <div className="period-filter">
          <input type="date" value={value.start} max={value.end || undefined} aria-label="Início"
            onChange={(e) => e.target.value && onChange({ ...value, start: e.target.value })} />
          <span>até</span>
          <input type="date" value={value.end} min={value.start || undefined} aria-label="Fim"
            onChange={(e) => e.target.value && onChange({ ...value, end: e.target.value })} />
        </div>
      )}
    </div>
  );
}

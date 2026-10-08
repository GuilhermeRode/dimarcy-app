import { useState } from "react";
import { addDays, localDate } from "../format";

const PRESETS = [
  { key: "7d", label: "7 dias", start: () => addDays(localDate(), -6) },
  { key: "month", label: "Este mês", start: () => `${localDate().slice(0, 8)}01` },
  { key: "year", label: "Este ano", start: () => `${new Date().getFullYear()}-01-01` },
];

export const defaultPeriod = () => ({ start: PRESETS[2].start(), end: localDate() });

export default function PeriodPicker({ value, onChange }) {
  const [preset, setPreset] = useState("year");
  return (
    <div className="period-block">
      <div className="period-chips" role="group" aria-label="Período">
        {PRESETS.map((p) => (
          <button key={p.key} type="button" className={`period-chip ${preset === p.key ? "on" : ""}`}
            onClick={() => { setPreset(p.key); onChange({ start: p.start(), end: localDate() }); }}>
            {p.label}
          </button>
        ))}
        <button type="button" className={`period-chip ${preset === "custom" ? "on" : ""}`}
          onClick={() => setPreset("custom")}>Personalizado</button>
      </div>
      {preset === "custom" && (
        <div className="period-filter">
          <input type="date" value={value.start} max={value.end} aria-label="Início"
            onChange={(e) => e.target.value && onChange({ ...value, start: e.target.value })} />
          <span>até</span>
          <input type="date" value={value.end} min={value.start} aria-label="Fim"
            onChange={(e) => e.target.value && onChange({ ...value, end: e.target.value })} />
        </div>
      )}
    </div>
  );
}

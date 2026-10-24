import { useState } from "react";
import { addDays, goalYearStart, localDate } from "../format";

const goalYear = Number(goalYearStart().slice(0, 4)); // Oct 2026 -> Sep 2027 shows as "2026/27"

const PRESETS = [
  { key: "7d", label: "7 dias", start: () => addDays(localDate(), -6), end: localDate },
  { key: "month", label: "Este mês", start: () => `${localDate().slice(0, 8)}01`, end: localDate },
  { key: "year", label: `Ano ${goalYear}/${String(goalYear + 1).slice(2)}`, start: goalYearStart, end: localDate },  // goal year, Oct -> Sep
];

export const defaultPeriod = () => ({ start: PRESETS[2].start(), end: localDate() });

// The active chip comes from `value` (so a parent can set the period too), except "Personalizado", which is a mode.
export default function PeriodPicker({ value, onChange, presets = PRESETS }) {
  const [custom, setCustom] = useState(false);
  const [picked, setPicked] = useState("year"); // defaultPeriod is the goal year
  // Two presets can cover the same dates (in October, "Este mês" = the goal year), so the clicked one wins.
  const matches = presets.filter((p) => p.start() === value.start && p.end() === value.end);
  const match = matches.find((p) => p.key === picked) || matches[0];
  const active = custom || !match ? "custom" : match.key;
  return (
    <div className="period-block">
      <div className="seg-control" role="group" aria-label="Período">
        {presets.map((p) => (
          <button key={p.key} type="button" className={active === p.key ? "on" : ""} aria-pressed={active === p.key}
            onClick={() => { setCustom(false); setPicked(p.key); onChange({ start: p.start(), end: p.end() }); }}>
            {p.label}
          </button>
        ))}
        <button type="button" className={active === "custom" ? "on" : ""} aria-pressed={active === "custom"}
          onClick={() => setCustom(true)}>Personalizado</button>
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

import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { money } from "../format";
import { ErrorBox } from "../components/ui";

const today = () => new Date().toISOString().slice(0, 10);
const startOfYear = () => `${new Date().getFullYear()}-01-01`;
const startOfMonth = () => {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
};
const addDays = (base, days) => {
  const d = new Date(`${base}T00:00:00`);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
};

const PRESETS = [
  { key: "7d", label: "7 dias", start: () => addDays(today(), -6) },
  { key: "month", label: "Este mês", start: startOfMonth },
  { key: "year", label: "Este ano", start: startOfYear },
];

export default function Revenue() {
  const [activePreset, setActivePreset] = useState("year");
  const [start, setStart] = useState(startOfYear());
  const [end, setEnd] = useState(today());
  const [d, setD] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/dashboard", { params: { start, end } })
      .then((r) => { setD(r.data); setError(""); })
      .catch((e) => setError(errorMessage(e)));
  }, [start, end]);

  function applyPreset(p) {
    setActivePreset(p.key);
    setStart(p.start());
    setEnd(today());
  }

  const sellers = d?.by_seller || [];
  const totals = sellers.reduce((a, s) => ({
    orders: a.orders + s.orders, pieces: a.pieces + s.pieces, value: a.value + s.value,
  }), { orders: 0, pieces: 0, value: 0 });

  return (
    <div className="page">
      <header className="dashboard-header">
        <div>
          <h1>Faturamento</h1>
          <p className="dashboard-greeting muted">Desempenho de vendas por vendedor no período.</p>
        </div>
        <div className="period-block">
          <div className="period-chips">
            {PRESETS.map((p) => (
              <button key={p.key} type="button" className={`period-chip ${activePreset === p.key ? "on" : ""}`}
                onClick={() => applyPreset(p)}>{p.label}</button>
            ))}
          </div>
          <div className="period-filter">
            <input type="date" value={start} aria-label="Início"
              onChange={(e) => { setActivePreset(""); setStart(e.target.value); }} />
            <span>até</span>
            <input type="date" value={end} aria-label="Fim"
              onChange={(e) => { setActivePreset(""); setEnd(e.target.value); }} />
          </div>
        </div>
      </header>
      <ErrorBox msg={error} />

      {d && (
        <>
          <section className="kpis">
            <div className="kpi kpi-highlight">
              <div className="kpi-header"><span>Faturamento total</span><span className="kpi-icon" aria-hidden="true">💰</span></div>
              <strong>{money(totals.value)}</strong>
            </div>
            <div className="kpis-secondary">
              <div className="kpi">
                <div className="kpi-header"><span>Vendedores ativos</span><span className="kpi-icon icon-teal" aria-hidden="true">🧑‍💼</span></div>
                <strong>{sellers.length}</strong>
              </div>
              <div className="kpi">
                <div className="kpi-header"><span>Pedidos</span><span className="kpi-icon icon-indigo" aria-hidden="true">🧾</span></div>
                <strong>{totals.orders}</strong>
              </div>
              <div className="kpi">
                <div className="kpi-header"><span>Peças</span><span className="kpi-icon icon-gold" aria-hidden="true">📦</span></div>
                <strong>{totals.pieces}</strong>
              </div>
            </div>
          </section>

          <section className="panel">
            <h3>Por vendedor</h3>
            {sellers.length ? (
              <table className="table">
                <thead>
                  <tr><th>Vendedor</th><th className="num">Pedidos</th><th className="num">Peças</th>
                    <th className="num">Ticket médio</th><th className="num">Faturamento</th></tr>
                </thead>
                <tbody>
                  {sellers.map((s) => (
                    <tr key={s.name}>
                      <td>{s.name}</td>
                      <td className="num">{s.orders}</td>
                      <td className="num">{s.pieces}</td>
                      <td className="num">{money(s.orders ? s.value / s.orders : 0)}</td>
                      <td className="num">{money(s.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="muted">Sem vendas no período.</p>}
          </section>
        </>
      )}
    </div>
  );
}

import { useState } from "react";
import { compactMoney, money } from "../format";
import { ErrorBox } from "../components/ui";
import Delta from "../components/Delta";
import PeriodPicker, { defaultPeriod } from "../components/PeriodPicker";
import TeamRanking, { SELLER_COLORS } from "../components/TeamRanking";
import usePeriodData from "../components/usePeriodData";

function topCities(cities, n = 5) {
  const top = cities.slice(0, n);
  const rest = cities.slice(n).reduce((t, c) => t + c.value, 0);
  return rest > 0 ? [...top, { name: "Outras", value: rest }] : top;
}

export default function Revenue() {
  const [period, setPeriod] = useState(defaultPeriod);
  const { data: d, error } = usePeriodData(period);
  const sellers = d?.by_seller || [];
  const withSales = sellers.map((s, i) => ({ ...s, color: SELLER_COLORS[i % SELLER_COLORS.length] })).filter((s) => s.value > 0);
  const cities = topCities(d?.by_city || []);
  const cityMax = Math.max(...cities.map((c) => c.value), 1);

  return (
    <div className="page">
      <header className="dashboard-header">
        <div>
          <h1>Faturamento</h1>
          <p className="dashboard-greeting muted">Desempenho de vendas no período.</p>
        </div>
        <PeriodPicker value={period} onChange={setPeriod} />
      </header>
      <ErrorBox msg={error} />
      {d && (
        <>
          <section className="hero revenue-hero">
            <div className="revenue-hero-top">
              <div className="hero-main">
                <span className="hero-label">Faturamento total</span>
                <strong className="hero-value">{money(d.kpis.revenue)}</strong>
                {d.previous_kpis.revenue > 0 && (
                  <span className="hero-delta"><Delta cur={d.kpis.revenue} prev={d.previous_kpis.revenue} /> vs. período anterior</span>
                )}
              </div>
              <div className="revenue-hero-kpis">
                <div><span>Pedidos</span><strong>{d.kpis.orders.toLocaleString("pt-BR")}</strong></div>
                <div><span>Peças</span><strong>{d.kpis.pieces.toLocaleString("pt-BR")}</strong></div>
                <div><span>Ticket médio</span><strong>{money(d.kpis.average_ticket)}</strong></div>
              </div>
            </div>
            {withSales.length > 0 && (
              <div className="share">
                <div className="share-bar">
                  {withSales.map((s) => <span key={s.id} title={s.name} style={{ flex: s.value, background: s.color }} />)}
                </div>
                <div className="share-legend">
                  {withSales.map((s) => (
                    <span key={s.id}><i style={{ background: s.color }} />
                      {s.name.split(" ")[0]} {Math.round((s.value / d.kpis.revenue) * 100)}%</span>
                  ))}
                </div>
              </div>
            )}
          </section>

          <TeamRanking title="Por vendedor" sellers={sellers} showGoalGap />

          <section className="panel">
            <h3>Por cidade</h3>
            {cities.length ? (
              <ul className="hbars">
                {cities.map((c) => (
                  <li key={c.name}>
                    <div><span>{c.name}</span><strong>{compactMoney(c.value)}</strong></div>
                    <span className="hbar"><span style={{ width: `${(c.value / cityMax) * 100}%` }} /></span>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">Sem vendas no período.</p>}
          </section>
        </>
      )}
    </div>
  );
}

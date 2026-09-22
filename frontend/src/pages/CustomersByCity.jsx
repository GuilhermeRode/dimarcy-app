import { useEffect, useMemo, useState } from "react";
import { ComposableMap, Geographies, Geography, Marker } from "react-simple-maps";
import { geoMercator } from "d3-geo";
import { api, errorMessage } from "../api";
import { money } from "../format";
import { ErrorBox } from "../components/ui";
import { cityCoords } from "../cityCoords";
import statesGeo from "../assets/br-states.geo.json";

const STATES = ["PR", "RS", "SC", "SP"];
const MAP_W = 560;
const MAP_H = 560;
const projection = geoMercator().fitSize([MAP_W, MAP_H], statesGeo);

function monthsAgo(n) {
  const d = new Date();
  d.setMonth(d.getMonth() - n);
  return d.toISOString().slice(0, 10);
}

export default function CustomersByCity() {
  const [customers, setCustomers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [stateFilter, setStateFilter] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.get("/customers"), api.get("/orders")])
      .then(([c, o]) => { setCustomers(c.data); setOrders(o.data); setError(""); })
      .catch((e) => setError(errorMessage(e)));
  }, []);

  const cutoff = monthsAgo(12);

  const cities = useMemo(() => {
    const lastOrderByCustomer = new Map();
    for (const o of orders) {
      const prev = lastOrderByCustomer.get(o.customer_id);
      if (!prev || o.date > prev) lastOrderByCustomer.set(o.customer_id, o.date);
    }
    const groups = new Map();
    for (const c of customers) {
      if (!c.city) continue;
      const state = (c.state || "").trim().toUpperCase();
      const key = `${c.city.trim()}/${state}`;
      const g = groups.get(key) || { name: key, city: c.city.trim(), state, total: 0, active: 0 };
      g.total += 1;
      const last = lastOrderByCustomer.get(c.id);
      if (last && last >= cutoff) g.active += 1;
      groups.set(key, g);
    }
    let list = [...groups.values()];
    if (stateFilter) list = list.filter((g) => g.state === stateFilter);
    list.sort((a, b) => b.active - a.active || b.total - a.total);
    return list;
  }, [customers, orders, stateFilter, cutoff]);

  const activeClients = cities.reduce((s, c) => s + c.active, 0);
  const totalCadastrados = customers.filter((c) => !stateFilter || (c.state || "").toUpperCase() === stateFilter).length;
  const statesCount = new Set(cities.map((c) => c.state).filter(Boolean)).size;
  const topCity = cities[0];
  const concentration = activeClients && topCity ? Math.round((topCity.active / activeClients) * 100) : 0;

  const revenue12mo = useMemo(() => {
    if (!stateFilter) return orders.filter((o) => o.date >= cutoff).reduce((s, o) => s + o.total, 0);
    const idsInState = new Set(customers.filter((c) => (c.state || "").toUpperCase() === stateFilter).map((c) => c.id));
    return orders.filter((o) => o.date >= cutoff && idsInState.has(o.customer_id)).reduce((s, o) => s + o.total, 0);
  }, [orders, customers, stateFilter, cutoff]);

  const maxActive = Math.max(1, ...cities.map((c) => c.active));
  const radius = (active) => (active === 0 ? 3 : 4 + (Math.sqrt(active) / Math.sqrt(maxActive)) * 16);

  return (
    <div className="page page-wide">
      <header className="page-header">
        <div>
          <h1>Clientes por cidade</h1>
          <p className="muted">Tamanho do círculo = clientes ativos (com pedido nos últimos 12 meses).</p>
        </div>
        <div className="period-chips">
          <button type="button" className={`period-chip ${!stateFilter ? "on" : ""}`} onClick={() => setStateFilter("")}>Todos</button>
          {STATES.map((uf) => (
            <button key={uf} type="button" className={`period-chip ${stateFilter === uf ? "on" : ""}`} onClick={() => setStateFilter(uf)}>{uf}</button>
          ))}
        </div>
      </header>
      <ErrorBox msg={error} />

      <section className="orders-kpis">
        <div className="kpi">
          <div className="kpi-header"><span>Clientes ativos</span></div>
          <strong>{activeClients}</strong>
          <span>de {totalCadastrados} cadastrados</span>
        </div>
        <div className="kpi">
          <div className="kpi-header"><span>Cidades</span></div>
          <strong>{cities.length}</strong>
          <span>em {statesCount} estado{statesCount === 1 ? "" : "s"}</span>
        </div>
        <div className="kpi">
          <div className="kpi-header"><span>Faturamento 12 meses</span></div>
          <strong>{money(revenue12mo)}</strong>
          <span>nas cidades exibidas</span>
        </div>
        <div className="kpi">
          <div className="kpi-header"><span>Concentração</span></div>
          <strong>{concentration}%</strong>
          <span>{topCity ? `em ${topCity.city}` : "—"}</span>
        </div>
      </section>

      <div className="city-map-layout">
        <section className="panel city-map-panel">
          <div className="panel-header"><h3>Mapa</h3><span className="muted">{stateFilter || "Sul e Sudeste"}</span></div>
          <ComposableMap width={MAP_W} height={MAP_H} projection={projection} style={{ width: "100%", height: "auto" }}>
            <Geographies geography={statesGeo}>
              {({ geographies }) => geographies.map((geo) => (
                <Geography key={geo.rsmKey} geography={geo}
                  fill={stateFilter && geo.properties.uf !== stateFilter ? "#eef2f9" : "#e4eaf6"}
                  stroke="#c7d3e8" strokeWidth={1}
                  style={{ default: { outline: "none" }, hover: { outline: "none" }, pressed: { outline: "none" } }} />
              ))}
            </Geographies>
            {cities.map((c) => {
              const coords = cityCoords(c.city, c.state);
              if (!coords) return null;
              const r = radius(c.active);
              return (
                <Marker key={c.name} coordinates={[coords[1], coords[0]]}>
                  <circle r={r} fill="rgba(47,111,237,.35)" stroke="#1d54c9" strokeWidth={1.5} />
                  <text textAnchor="middle" y={-r - 6} fontSize={11} fontWeight={600} fill="#16233d">{c.city}</text>
                </Marker>
              );
            })}
          </ComposableMap>
          <div className="city-map-legend">
            {[2, 8, 20].map((n) => (
              <span key={n} className="city-map-legend-item">
                <span className="city-map-legend-dot" style={{ width: radius(n) * 2, height: radius(n) * 2 }} />
                <small>{n}</small>
              </span>
            ))}
            <span className="muted">clientes ativos por cidade</span>
          </div>
        </section>

        <section className="panel">
          <div className="panel-header"><h3>Ranking</h3><span className="muted">{cities.length} cidades</span></div>
          {cities.length ? (
            <ol className="ranking">
              {cities.map((c, k) => (
                <li key={c.name}>
                  <div className="ranking-row">
                    <span className="ranking-left">
                      <span className={`ranking-rank ${k === 0 ? "gold" : ""}`}>{k + 1}</span>
                      <span className="ranking-name">{c.city}/{c.state}</span>
                    </span>
                    <span className="ranking-value">{c.active}</span>
                  </div>
                  <div className="ranking-bar"><span style={{ width: `${(c.active / maxActive) * 100}%` }} /></div>
                  <div className="ranking-detail">{c.total} cliente{c.total > 1 ? "s" : ""} cadastrado{c.total > 1 ? "s" : ""}</div>
                </li>
              ))}
            </ol>
          ) : <p className="muted">Nenhum cliente com cidade cadastrada.</p>}
        </section>
      </div>
    </div>
  );
}

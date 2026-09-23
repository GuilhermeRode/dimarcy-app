import { useEffect, useMemo, useRef, useState } from "react";
import { ComposableMap, Geographies, Geography, Marker, ZoomableGroup } from "react-simple-maps";
import { geoMercator } from "d3-geo";
import { api, errorMessage } from "../api";
import { money } from "../format";
import { ErrorBox } from "../components/ui";
import statesGeo from "../assets/br-states.geo.json";

const STATES = ["GO", "MG", "PR", "RJ", "RS", "SC", "SP"];
const MAP_W = 620;
const MAP_H = 600;
const MIN_ZOOM = 1;
const MAX_ZOOM = 8;
const projection = geoMercator().fitSize([MAP_W, MAP_H], statesGeo);

const STATE_COLOR_LOW = [232, 240, 254]; // --accent-light
const STATE_COLOR_HIGH = [29, 84, 201]; // --accent-strong

function stateColor(count, max) {
  const t = max > 0 ? Math.min(1, count / max) : 0;
  const [r, g, b] = STATE_COLOR_LOW.map((v, i) => Math.round(v + (STATE_COLOR_HIGH[i] - v) * t));
  return `rgb(${r}, ${g}, ${b})`;
}

function monthsAgo(n) {
  const d = new Date();
  d.setMonth(d.getMonth() - n);
  return d.toISOString().slice(0, 10);
}

export default function CustomersByCity() {
  const [customers, setCustomers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [stateFilter, setStateFilter] = useState("");
  const [viewMode, setViewMode] = useState("both"); // "both" | "cities" | "states"
  const [error, setError] = useState("");
  const [zoom, setZoom] = useState(1);
  const [hovered, setHovered] = useState(null); // { city, x, y }
  const [selected, setSelected] = useState(null); // city key
  const mapWrapRef = useRef(null);

  useEffect(() => {
    Promise.all([api.get("/customers"), api.get("/orders")])
      .then(([c, o]) => { setCustomers(c.data); setOrders(o.data); setError(""); })
      .catch((e) => setError(errorMessage(e)));
  }, []);

  const cutoff = monthsAgo(12);

  const lastOrderByCustomer = useMemo(() => {
    const m = new Map();
    for (const o of orders) {
      const prev = m.get(o.customer_id);
      if (!prev || o.date > prev) m.set(o.customer_id, o.date);
    }
    return m;
  }, [orders]);

  const stateActive = useMemo(() => {
    const m = new Map();
    for (const c of customers) {
      const state = (c.state || "").trim().toUpperCase();
      if (!state) continue;
      const last = lastOrderByCustomer.get(c.id);
      if (last && last >= cutoff) m.set(state, (m.get(state) || 0) + 1);
    }
    return m;
  }, [customers, lastOrderByCustomer, cutoff]);
  const maxStateActive = Math.max(1, ...STATES.map((s) => stateActive.get(s) || 0));

  const cities = useMemo(() => {
    const groups = new Map();
    for (const c of customers) {
      if (!c.city) continue;
      const state = (c.state || "").trim().toUpperCase();
      const key = `${c.city.trim()}/${state}`;
      const g = groups.get(key) || { name: key, city: c.city.trim(), state, total: 0, active: 0, lat: null, lng: null };
      g.total += 1;
      if (g.lat == null && c.lat != null && c.lng != null) { g.lat = c.lat; g.lng = c.lng; }
      const last = lastOrderByCustomer.get(c.id);
      if (last && last >= cutoff) g.active += 1;
      groups.set(key, g);
    }
    let list = [...groups.values()];
    if (stateFilter) list = list.filter((g) => g.state === stateFilter);
    list.sort((a, b) => b.active - a.active || b.total - a.total);
    return list;
  }, [customers, lastOrderByCustomer, stateFilter, cutoff]);

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
  const radius = (active) => (active === 0 ? 3 : 4 + (Math.sqrt(active) / Math.sqrt(maxActive)) * 15);

  function pointerPos(e) {
    const rect = mapWrapRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  const showCities = viewMode !== "states";
  const showStates = viewMode !== "cities";

  return (
    <div className="page page-wide">
      <header className="page-header">
        <div>
          <h1>Clientes por cidade</h1>
          <p className="muted">Clientes ativos = com pedido nos últimos 12 meses.</p>
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
          <span>{stateFilter ? "nas cidades exibidas" : "todas as cidades"}</span>
        </div>
        <div className="kpi">
          <div className="kpi-header"><span>Concentração</span></div>
          <strong>{concentration}%</strong>
          <span>{topCity ? `em ${topCity.city}` : "—"}</span>
        </div>
      </section>

      <div className="city-map-layout">
        <section className="panel city-map-panel">
          <div className="panel-header">
            <h3>Mapa</h3>
            <div className="period-chips">
              <button type="button" className={`period-chip ${viewMode === "both" ? "on" : ""}`} onClick={() => setViewMode("both")}>Estados + cidades</button>
              <button type="button" className={`period-chip ${viewMode === "cities" ? "on" : ""}`} onClick={() => setViewMode("cities")}>Só cidades</button>
              <button type="button" className={`period-chip ${viewMode === "states" ? "on" : ""}`} onClick={() => setViewMode("states")}>Só estados</button>
            </div>
          </div>
          <div className="city-map-canvas" ref={mapWrapRef}>
            <div className="city-map-zoom">
              <button type="button" className="btn-x" onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z + 1))} aria-label="Aumentar zoom">+</button>
              <button type="button" className="btn-x" onClick={() => setZoom((z) => Math.max(MIN_ZOOM, z - 1))} aria-label="Diminuir zoom">−</button>
              <button type="button" className="btn-x" onClick={() => setZoom(1)} aria-label="Redefinir zoom" title="Redefinir">⤢</button>
            </div>
            <ComposableMap width={MAP_W} height={MAP_H} projection={projection} style={{ width: "100%", height: "auto" }}>
              <defs>
                <radialGradient id="bubbleGrad" cx="35%" cy="30%" r="70%">
                  <stop offset="0%" stopColor="#6fa0f7" stopOpacity="0.95" />
                  <stop offset="100%" stopColor="#1d54c9" stopOpacity="0.6" />
                </radialGradient>
                <radialGradient id="bubbleGradSelected" cx="35%" cy="30%" r="70%">
                  <stop offset="0%" stopColor="#ffcf7a" stopOpacity="0.95" />
                  <stop offset="100%" stopColor="#b8862f" stopOpacity="0.65" />
                </radialGradient>
              </defs>
              <ZoomableGroup zoom={zoom} minZoom={MIN_ZOOM} maxZoom={MAX_ZOOM} onMoveEnd={({ zoom: z }) => setZoom(z)}>
                <Geographies geography={statesGeo}>
                  {({ geographies }) => geographies.map((geo) => {
                    const uf = geo.properties.uf;
                    const muted = stateFilter && uf !== stateFilter;
                    const fill = !showStates || muted ? "#eef2f9" : stateColor(stateActive.get(uf) || 0, maxStateActive);
                    return (
                      <Geography key={geo.rsmKey} geography={geo} fill={fill} stroke="#c7d3e8" strokeWidth={0.75}
                        style={{
                          default: { outline: "none", transition: "fill .15s ease" },
                          hover: { outline: "none", fill: muted ? "#eef2f9" : "#9db8ee" },
                          pressed: { outline: "none" },
                        }} />
                    );
                  })}
                </Geographies>
                {showCities && cities.map((c) => {
                  if (c.lat == null || c.lng == null) return null;
                  const r = radius(c.active) / Math.sqrt(zoom);
                  const isSelected = selected === c.name;
                  return (
                    <Marker key={c.name} coordinates={[c.lng, c.lat]}
                      onClick={() => setSelected(isSelected ? null : c.name)}
                      onMouseEnter={(e) => setHovered({ city: c, ...pointerPos(e) })}
                      onMouseMove={(e) => setHovered({ city: c, ...pointerPos(e) })}
                      onMouseLeave={() => setHovered(null)}>
                      <circle className="city-bubble" r={r}
                        fill={isSelected ? "url(#bubbleGradSelected)" : "url(#bubbleGrad)"}
                        stroke={isSelected ? "#9a5b12" : "#1d54c9"} strokeWidth={1.25} />
                    </Marker>
                  );
                })}
              </ZoomableGroup>
            </ComposableMap>
            {hovered && (
              <div className="city-map-tooltip" style={{ left: hovered.x + 14, top: hovered.y + 10 }}>
                <strong>{hovered.city.city}/{hovered.city.state}</strong>
                <span>{hovered.city.active} ativo{hovered.city.active === 1 ? "" : "s"} · {hovered.city.total} cadastrado{hovered.city.total === 1 ? "" : "s"}</span>
              </div>
            )}
          </div>
          <div className="city-map-legend">
            {showStates && (
              <span className="city-map-legend-item">
                <span className="city-map-legend-gradient" />
                <small>Ativos por estado · até {maxStateActive}</small>
              </span>
            )}
            {showCities && (
              <>
                {[2, 8, 20].map((n) => (
                  <span key={n} className="city-map-legend-item">
                    <span className="city-map-legend-dot" style={{ width: radius(n) * 2, height: radius(n) * 2 }} />
                    <small>{n}</small>
                  </span>
                ))}
                <span className="muted">clientes ativos por cidade</span>
              </>
            )}
            <span className="muted city-map-hint">Arraste para mover · role para aproximar</span>
          </div>
        </section>

        <section className="panel city-map-ranking">
          <div className="panel-header"><h3>Ranking</h3><span className="muted">{cities.length} cidades</span></div>
          {cities.length ? (
            <ol className="ranking ranking-scroll">
              {cities.map((c, k) => (
                <li key={c.name} className={selected === c.name ? "ranking-selected" : ""}
                  onClick={() => setSelected(selected === c.name ? null : c.name)}>
                  <div className="ranking-row">
                    <span className="ranking-left">
                      <span className={`ranking-rank ${k === 0 ? "gold" : ""}`}>{k + 1}</span>
                      <span className="ranking-name">{c.city}/{c.state}</span>
                    </span>
                    <span className="ranking-value">{c.active}</span>
                  </div>
                  <div className="ranking-bar"><span style={{ width: `${(c.active / maxActive) * 100}%` }} /></div>
                  <div className="ranking-detail">
                    {c.total} cliente{c.total > 1 ? "s" : ""} cadastrado{c.total > 1 ? "s" : ""}
                    {c.lat == null && " · fora do mapa (endereço não localizado)"}
                  </div>
                </li>
              ))}
            </ol>
          ) : <p className="muted">Nenhum cliente com cidade cadastrada.</p>}
        </section>
      </div>
    </div>
  );
}

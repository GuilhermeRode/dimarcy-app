import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, ZoomControl, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api, errorMessage } from "../api";
import { compactMoney, localDate, money, plural } from "../format";
import { ErrorBox } from "../components/ui";
import statesGeo from "../assets/br-states.geo.json";

const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const TILE_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

const PERIODS = [[30, "30 dias"], [90, "90 dias"], [365, "12 meses"]];
// Average-ticket classes, light to dark: up to R$ 3 mil, 3–5 mil, 5–10 mil, above 10 mil.
const TICKET_COLORS = ["#c9d3e6", "#8ea0c4", "#4f6491", "#0c2140"];
const TICKET_CUTS = [3000, 5000, 10000];
const TICKET_LABELS = ["Até R$ 3 mil", "R$ 3 mil – R$ 5 mil", "R$ 5 mil – R$ 10 mil", "Acima de R$ 10 mil"];
const brazilBounds = L.geoJSON(statesGeo).getBounds();

const ticketClass = (ticket) => TICKET_CUTS.filter((c) => ticket > c).length;

function daysAgo(iso) {
  if (!iso) return null;
  return Math.round((new Date(`${localDate()}T00:00:00`) - new Date(`${iso}T00:00:00`)) / 86400000);
}

function FitTo({ points, focus }) {
  const map = useMap();
  useEffect(() => {
    if (focus) { map.flyTo([focus.lat, focus.lng], Math.max(map.getZoom(), 9)); return; }
    const pts = points.filter((p) => p.lat != null);
    if (!pts.length) return; // the map already opens on Brazil
    // Not animated: Leaflet drops a new view requested while a zoom animation is still running.
    // Extra bottom padding keeps bubbles out from under the legend (bottom-left corner).
    const legendOverMap = map.getSize().y > 500; // on narrow screens the legend sits below the map
    map.fitBounds(L.latLngBounds(pts.map((p) => [p.lat, p.lng])),
      { paddingTopLeft: [40, 40], paddingBottomRight: [40, legendOverMap ? 270 : 40], maxZoom: 9, animate: false });
  }, [points, focus, map]);
  return null;
}

export default function CustomersByCity() {
  const [rows, setRows] = useState([]);
  const [sellers, setSellers] = useState([]);
  const [days, setDays] = useState(365);
  const [ownerId, setOwnerId] = useState("");
  const [selected, setSelected] = useState(null); // "city/UF"
  const [error, setError] = useState("");

  useEffect(() => { api.get("/users").then((r) => setSellers(r.data.filter((u) => u.role === "seller"))); }, []);
  useEffect(() => {
    api.get("/customers/by-city", { params: { days, ...(ownerId ? { owner_id: ownerId } : {}) } })
      .then((r) => { setRows(r.data); setError(""); setSelected(null); })
      .catch((e) => setError(errorMessage(e)));
  }, [days, ownerId]);

  const cities = useMemo(() => rows.map((r) => ({ ...r, key: `${r.city}/${r.state}` }))
    .sort((a, b) => b.active - a.active || (b.last_order_date || "").localeCompare(a.last_order_date || "")), [rows]);
  const maxActive = Math.max(1, ...cities.map((c) => c.active));
  const maxRevenue = Math.max(1, ...cities.map((c) => c.revenue));
  const totals = cities.reduce((t, c) => ({ active: t.active + c.active, registered: t.registered + c.registered }), { active: 0, registered: 0 });
  const radius = (c) => (c.active ? 7 + (Math.sqrt(c.active) / Math.sqrt(maxActive)) * 17 : 6);
  const color = (c) => (c.active ? TICKET_COLORS[ticketClass(c.average_ticket)] : "#ffffff");
  const focus = cities.find((c) => c.key === selected && c.lat != null) || null;

  return (
    <div className="page page-wide">
      <header className="page-header">
        <div>
          <h1>Clientes por cidade</h1>
          <p className="muted">Ativos = clientes com pelo menos uma compra no período.</p>
        </div>
      </header>

      <section className="map-filters">
        <label className="map-filter">
          <span>Vendedor</span>
          <select value={ownerId} onChange={(e) => setOwnerId(e.target.value)}>
            <option value="">Todos</option>
            {sellers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <div className="map-filter">
          <span>Período</span>
          <div className="segmented" role="group" aria-label="Período">
            {PERIODS.map(([d, label]) => (
              <button key={d} type="button" className={days === d ? "on" : ""} onClick={() => setDays(d)}>{label}</button>
            ))}
          </div>
        </div>
      </section>
      <ErrorBox msg={error} />

      <div className="city-map-layout">
        <section className="city-map-canvas">
          {/* Size comes from CSS (.city-map-canvas .leaflet-container), so phones can override it. */}
          <MapContainer bounds={brazilBounds} zoomControl={false} scrollWheelZoom>
            <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
            <ZoomControl position="topleft" />
            <FitTo points={cities} focus={focus} />
            {cities.filter((c) => c.lat != null).map((c) => (
              <CircleMarker key={c.key} center={[c.lat, c.lng]} radius={radius(c)}
                fillColor={color(c)} fillOpacity={c.active ? 0.9 : 0.6}
                color={c.key === selected ? "#2563eb" : c.active ? "#ffffff" : "#b6c0d1"}
                weight={c.key === selected ? 3 : 1.5}
                eventHandlers={{ click: () => setSelected(c.key === selected ? null : c.key) }}>
                <Tooltip direction="top" offset={[0, -radius(c)]}>
                  <strong>{c.city}/{c.state}</strong><br />
                  Ticket médio: {c.average_ticket != null ? money(c.average_ticket) : "—"}<br />
                  {plural(c.active, "ativo", "ativos")} · {plural(c.registered, "cadastrado", "cadastrados")}
                </Tooltip>
              </CircleMarker>
            ))}
          </MapContainer>

          <div className="map-legend">
            <strong>Ticket médio por cidade</strong>
            {TICKET_LABELS.map((label, i) => (
              <span key={i}><i style={{ background: TICKET_COLORS[i] }} />{label}</span>
            ))}
            <small>Cor = ticket médio · Tamanho = nº de clientes ativos</small>
            <span><i className="hollow" />Sem clientes ativos</span>
            <div className="map-legend-totals">
              <div><small>Ativos</small><b className="ok">{totals.active}</b></div>
              <div><small>Cadastrados</small><b>{totals.registered}</b></div>
            </div>
          </div>
        </section>

        <section className="city-rank">
          <header><strong>Ranking por cidade</strong><span className="muted">{plural(cities.length, "cidade", "cidades")}</span></header>
          <ol>
            {cities.map((c) => {
              const ago = daysAgo(c.last_order_date);
              return (
                <li key={c.key} className={c.key === selected ? "on" : ""}>
                  <button type="button" onClick={() => setSelected(c.key === selected ? null : c.key)}>
                    <div className="city-rank-top">
                      <span className="city-rank-name">
                        <i style={{ background: c.active ? color(c) : "#dfe6f1" }} />
                        <strong>{c.city}</strong><small>{c.state}</small>
                      </span>
                      <strong>{c.revenue ? compactMoney(c.revenue) : "—"}</strong>
                    </div>
                    <span className="city-rank-bar"><span style={{ width: `${(c.revenue / maxRevenue) * 100}%` }} /></span>
                    <div className="city-rank-sub">
                      <span>{c.active} ativo{c.active === 1 ? "" : "s"} · {c.registered} cadastrado{c.registered === 1 ? "" : "s"}</span>
                      <span>{ago == null ? "Sem pedidos" : ago === 0 ? "Último pedido hoje" : `Último pedido há ${plural(ago, "dia", "dias")}`}</span>
                    </div>
                    {c.lat == null && <small className="muted">Fora do mapa (endereço não localizado)</small>}
                  </button>
                </li>
              );
            })}
          </ol>
          {!cities.length && <p className="muted">Nenhum cliente com cidade cadastrada.</p>}
        </section>
      </div>
    </div>
  );
}

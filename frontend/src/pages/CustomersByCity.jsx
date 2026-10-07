import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Tooltip, ZoomControl, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api, errorMessage } from "../api";
import { compactMoney, localDate, money, plural } from "../format";
import { ErrorBox } from "../components/ui";
import statesGeo from "../assets/br-states.geo.json";

// Light gray basemap so the colored bubbles stand out (Esri World Light Gray: base + place names).
const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas";
const TILE_URL = `${ESRI}/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`;
const LABELS_URL = `${ESRI}/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`;
const TILE_ATTRIBUTION = "Tiles &copy; Esri";

const PERIODS = [[30, "30 dias"], [90, "90 dias"], [365, "12 meses"]];
// Average-ticket classes, light to dark (quartiles of the cities with active customers).
const TICKET_COLORS = ["#c9d3e6", "#8ea0c4", "#4f6491", "#0c2140"];
const brazilBounds = L.geoJSON(statesGeo).getBounds();

function quartiles(values) {
  const v = [...values].sort((a, b) => a - b);
  if (!v.length) return [];
  const at = (p) => v[Math.min(v.length - 1, Math.floor(p * v.length))];
  return [at(0.25), at(0.5), at(0.75)];
}
const ticketClass = (ticket, cuts) => cuts.filter((c) => ticket > c).length;

function daysAgo(iso) {
  if (!iso) return null;
  return Math.round((new Date(`${localDate()}T00:00:00`) - new Date(`${iso}T00:00:00`)) / 86400000);
}

function FitTo({ points, focus }) {
  const map = useMap();
  useEffect(() => {
    if (focus) { map.flyTo([focus.lat, focus.lng], Math.max(map.getZoom(), 9)); return; }
    const pts = points.filter((p) => p.lat != null);
    // Extra bottom padding keeps bubbles out from under the legend (bottom-left corner).
    map.fitBounds(pts.length ? L.latLngBounds(pts.map((p) => [p.lat, p.lng])) : brazilBounds,
      { paddingTopLeft: [40, 40], paddingBottomRight: [40, 270], maxZoom: 9 });
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
  const cuts = useMemo(() => quartiles(cities.filter((c) => c.active).map((c) => c.average_ticket)), [cities]);
  const maxActive = Math.max(1, ...cities.map((c) => c.active));
  const maxRevenue = Math.max(1, ...cities.map((c) => c.revenue));
  const totals = cities.reduce((t, c) => ({ active: t.active + c.active, registered: t.registered + c.registered }), { active: 0, registered: 0 });
  const radius = (c) => (c.active ? 7 + (Math.sqrt(c.active) / Math.sqrt(maxActive)) * 17 : 6);
  const color = (c) => (c.active ? TICKET_COLORS[ticketClass(c.average_ticket, cuts)] : "#ffffff");
  const focus = cities.find((c) => c.key === selected && c.lat != null) || null;
  const legend = cuts.length ? [
    `Até ${compactMoney(cuts[0])}`, `${compactMoney(cuts[0])} – ${compactMoney(cuts[1])}`,
    `${compactMoney(cuts[1])} – ${compactMoney(cuts[2])}`, `Acima de ${compactMoney(cuts[2])}`,
  ] : [];

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
          <MapContainer bounds={brazilBounds} zoomControl={false} scrollWheelZoom style={{ width: "100%", height: "100%" }}>
            <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} maxZoom={16} />
            <TileLayer url={LABELS_URL} maxZoom={16} />
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
            {legend.map((label, i) => (
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

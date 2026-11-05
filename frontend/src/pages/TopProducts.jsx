import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { money, plural } from "../format";
import { EmptyState, ErrorBox } from "../components/ui";
import { ProductThumb, RefColors } from "../components/ColorStrip";
import PeriodPicker, { defaultPeriod } from "../components/PeriodPicker";
import usePeriodData from "../components/usePeriodData";
import { useSort } from "../components/useSort";

const plain = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

// Every reference sold in the period, opened from "Referências mais vendidas" on the Painel
export default function TopProducts() {
  const location = useLocation();
  const [period, setPeriod] = useState(() => location.state?.period || defaultPeriod());
  const { data: d, error } = usePeriodData(period);
  const [search, setSearch] = useState("");

  const all = (d?.top_products || []).map((p, i) => ({ ...p, rank: i + 1 }));
  const totalPieces = d?.kpis.pieces || 0;
  const q = plain(search.trim());
  const rows = q ? all.filter((p) => plain(`${p.reference} ${p.description}`).includes(q)) : all;
  const { sorted, sortHeader } = useSort(rows, {
    rank: (p) => p.rank,
    reference: (p) => p.reference,
    orders: (p) => p.orders,
    pieces: (p) => p.pieces,
    value: (p) => p.value,
    average: (p) => p.value / p.pieces,
  }, { key: "rank", dir: 1 });
  const sum = (k) => rows.reduce((t, p) => t + p[k], 0);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <Link className="back-link" to="/">← Painel</Link>
          <h1>Referências mais vendidas</h1>
          <p className="muted">Peças, pedidos e cores de cada referência vendida no período.</p>
        </div>
        <PeriodPicker value={period} onChange={setPeriod} />
      </header>
      <ErrorBox msg={error} />

      <section className="panel panel-table">
        <div className="table-toolbar">
          <input className="toolbar-search" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por referência ou descrição" aria-label="Buscar referência" />
          {d && (
            <span className="muted toolbar-summary">
              {plural(rows.length, "referência", "referências")} · {plural(sum("pieces"), "peça", "peças")} · {money(sum("value"))}
            </span>
          )}
        </div>

        {d && !rows.length ? (
          <EmptyState text={all.length ? "Nenhuma referência encontrada." : "Nenhuma venda no período."} />
        ) : d && (
          <div className="table-scroll">
            <table className="table table-refs">
              <thead>
                <tr>
                  {sortHeader("rank", "#", "num")}
                  {sortHeader("reference", "Referência")}
                  <th>Cores</th>
                  {sortHeader("orders", "Pedidos", "num")}
                  {sortHeader("pieces", "Peças", "num")}
                  {sortHeader("value", "Valor", "num")}
                  {sortHeader("average", "Preço médio", "num")}
                </tr>
              </thead>
              <tbody>
                {sorted.map((p) => (
                  <tr key={p.reference}>
                    <td className="num muted">{p.rank}</td>
                    <td>
                      <span className="ref-cell">
                        <ProductThumb url={p.thumb_url} />
                        <span className="cell-stack">
                          <span className="ref">{p.reference}</span>
                          <span className="cell-sub">{p.description}</span>
                        </span>
                      </span>
                    </td>
                    <td>
                      <RefColors className="ref-colors" colors={p.colors} total={p.pieces} />
                    </td>
                    <td className="num">{p.orders}</td>
                    <td className="num">
                      <strong>{p.pieces.toLocaleString("pt-BR")}</strong>
                      <span className="cell-sub ref-share">{Math.round((p.pieces / Math.max(totalPieces, 1)) * 100)}% das peças</span>
                    </td>
                    <td className="num"><strong>{money(p.value)}</strong></td>
                    <td className="num muted">{money(p.value / p.pieces)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

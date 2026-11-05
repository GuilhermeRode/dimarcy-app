import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { initials, utcDateBR } from "../format";
import { ErrorBox, PillSelect } from "../components/ui";
import { DISCARD_REASONS } from "./Leads";
import { useSort } from "../components/useSort";

// Descartados: who took each store out of Prospecção, when and why (admin: everyone's; seller: their own)
export default function DiscardedLeads() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");
  const [seller, setSeller] = useState("");
  const nav = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  useEffect(() => {
    api.get("/leads/discarded").then((r) => setRows(r.data)).catch((e) => setError(errorMessage(e)));
  }, []);

  const people = [...new Map((rows || []).map((r) => [String(r.user_id), r.user_name])).entries()]
    .sort((a, b) => a[1].localeCompare(b[1], "pt-BR"));
  const shown = (rows || []).filter((r) => !seller || String(r.user_id) === seller);
  // click a column to sort (same as Pedidos); opens newest first
  const { sorted, sortHeader } = useSort(shown, {
    name: (r) => r.name,
    city: (r) => `${r.city}/${r.state}`,
    reason: (r) => DISCARD_REASONS[r.reason] ?? r.reason,
    user: (r) => r.user_name,
    date: (r) => r.discarded_at,
  }, { key: "date", dir: -1 });

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Descartados</h1>
          <p className="muted">{isAdmin ? "Lojas tiradas da Prospecção pela equipe: quem descartou, quando e por quê." : "Lojas que você descartou e o motivo."}</p>
        </div>
        <div className="header-actions">
          <button className="btn" onClick={() => nav("/leads")}>{isAdmin ? "← Prospecção" : "← Oportunidades"}</button>
        </div>
      </header>
      <ErrorBox msg={error} />

      {isAdmin && people.length > 1 && (
        <section className="filters-bar">
          <div className="filters-row">
            <PillSelect label="Vendedor" value={seller} onChange={setSeller} options={[["", "Todos"], ...people]} />
          </div>
        </section>
      )}

      {rows && !shown.length ? <p className="customers-empty">Nenhuma loja descartada.</p> : (
        <div className="table-scroll">
          <table className="table table-orders table-discarded">
            <thead>
              <tr>
                {sortHeader("name", "Loja")}
                {sortHeader("city", "Cidade")}
                {sortHeader("reason", "Motivo")}
                {isAdmin && sortHeader("user", "Descartado por")}
                {sortHeader("date", "Data", "num")}
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr key={r.id}>
                  <td><span className="customers-cell-main">
                    <span className="customer-avatar">{initials(r.name)}</span><strong>{r.name}</strong>
                  </span></td>
                  <td>{r.city}/{r.state}</td>
                  <td><span className="discard-why">
                    <strong>{DISCARD_REASONS[r.reason] ?? r.reason}</strong>
                    {r.notes && <small>{r.notes}</small>}
                  </span></td>
                  {isAdmin && <td>{r.user_name}</td>}
                  <td className="num muted">{utcDateBR(r.discarded_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

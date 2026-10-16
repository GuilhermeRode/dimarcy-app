import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import { addDays, dateBR, localDate, money, orderNumber } from "../format";
import { EmptyState, ErrorBox, Field, Modal, useConfirm } from "../components/ui";
import RevenueTabs from "../components/RevenueTabs";
import PeriodPicker from "../components/PeriodPicker";

// Same list as PAYABLE_CATEGORIES in backend/app/models.py
const PAYABLE_CATEGORIES = ["Matéria-prima", "Aluguel", "Salários", "Impostos", "Energia", "Manutenção", "Outros"];
const PAYMENT_METHODS = ["Boleto", "Pix", "Transferência", "Cheque", "Dinheiro", "Cartão"];
const STATUS_LABEL = { open: "Em aberto", overdue: "Vencida", paid: "Paga" };
const STATUS_FILTERS = [["open", "Em aberto"], ["overdue", "Vencidas"], ["paid", "Pagas"], ["all", "Todas"]];
// Due-date periods look ahead (unlike the sales ones); "Todos" = no date filter
const monthEnd = () => { const d = new Date(); return localDate(new Date(d.getFullYear(), d.getMonth() + 1, 0)); };
const DUE_PRESETS = [
  { key: "all", label: "Todos", start: () => "", end: () => "" },
  { key: "7d", label: "Próximos 7 dias", start: localDate, end: () => addDays(localDate(), 7) },
  { key: "month", label: "Este mês", start: () => `${localDate().slice(0, 8)}01`, end: monthEnd },
];

export const EntryStatus = ({ s }) => <span className={`tag ${s === "overdue" ? "tag-warning" : ""}`}>{STATUS_LABEL[s]}</span>;

// Keeps a value that isn't in the list (e.g. a payment method typed on an old order) selectable
const withValue = (list, v) => (v && !list.includes(v) ? [...list, v] : list);

export function PayModal({ entry, onClose, onDone }) {
  const [f, setF] = useState({ paid_at: localDate(), paid_amount: entry.amount, payment_method: entry.payment_method || "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(e) {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      await api.post(`/finance/entries/${entry.id}/pay`, {
        paid_at: f.paid_at, paid_amount: Number(f.paid_amount), payment_method: f.payment_method || null,
      });
      onDone();
    } catch (err) { setError(errorMessage(err)); setBusy(false); }
  }

  return (
    <Modal title={`Dar baixa · ${entry.description}`} onClose={onClose}>
      <form onSubmit={save} className="form-grid">
        <Field label="Data do pagamento">
          <input type="date" required value={f.paid_at} onChange={(e) => setF({ ...f, paid_at: e.target.value })} />
        </Field>
        <Field label="Valor pago (R$)">
          <input type="number" step="0.01" min="0.01" required value={f.paid_amount}
            onChange={(e) => setF({ ...f, paid_amount: e.target.value })} />
        </Field>
        <Field label="Forma de pagamento" span={2}>
          <select value={f.payment_method} onChange={(e) => setF({ ...f, payment_method: e.target.value })}>
            <option value="">—</option>
            {withValue(PAYMENT_METHODS, entry.payment_method).map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </Field>
        <div className="span-2"><ErrorBox msg={error} /></div>
        <div className="actions span-2"><button className="btn btn-primary" disabled={busy}>Confirmar baixa</button></div>
      </form>
    </Modal>
  );
}

const emptyEntry = () => ({ description: "", amount: "", due_date: localDate(), payment_method: "", notes: "", supplier: "",
  category: "Outros", order_number: "", repeat_months: 1 });

function EntryModal({ kind, entry, onClose, onDone }) {
  const [confirmDialog, ask] = useConfirm();
  const isNew = !entry;
  const payable = kind === "payable";
  const paid = Boolean(entry?.paid_at);
  const [f, setF] = useState(() => (entry ? { ...emptyEntry(), ...entry, supplier: entry.supplier || "", notes: entry.notes || "",
    payment_method: entry.payment_method || "", category: entry.category || "Outros" } : emptyEntry()));
  const [split, setSplit] = useState(null); // { amount, due_date } while splitting
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const input = (k) => ({ value: f[k] ?? "", onChange: (e) => setF({ ...f, [k]: e.target.value }) });

  async function run(request) {
    setError(""); setBusy(true);
    try { await request(); onDone(); } catch (err) { setError(errorMessage(err)); setBusy(false); }
  }

  function save(e) {
    e.preventDefault();
    const body = {
      description: f.description, amount: Number(f.amount), due_date: f.due_date,
      payment_method: f.payment_method || null, notes: f.notes || null,
      supplier: payable ? f.supplier || null : null, category: payable ? f.category : null,
    };
    run(() => (isNew
      ? api.post("/finance/entries", { ...body, kind, repeat_months: Number(f.repeat_months) || 1,
          order_id: !payable && f.order_number ? Number(f.order_number) : null })
      : api.put(`/finance/entries/${entry.id}`, body)));
  }

  async function remove() {
    if (!(await ask({ title: "Excluir este lançamento?", message: entry.description, confirmLabel: "Excluir", danger: true }))) return;
    run(() => api.delete(`/finance/entries/${entry.id}`));
  }

  const title = isNew ? (payable ? "Lançar conta a pagar" : "Lançar conta a receber") : entry.description;
  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={save} className="form-grid">
        <Field label="Descrição" span={2}><input required maxLength={200} {...input("description")} /></Field>
        {payable ? (
          <>
            <Field label="Fornecedor / favorecido"><input maxLength={160} {...input("supplier")} /></Field>
            <Field label="Categoria">
              <select {...input("category")}>{PAYABLE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select>
            </Field>
          </>
        ) : isNew && (
          <Field label="Nº do pedido (opcional)" span={2}>
            <input inputMode="numeric" {...input("order_number")} onChange={(e) => setF({ ...f, order_number: e.target.value.replace(/\D/g, "") })} />
          </Field>
        )}
        <Field label="Valor (R$)">
          <input type="number" step="0.01" min="0.01" required disabled={paid} {...input("amount")} />
        </Field>
        <Field label={isNew ? "1º vencimento" : "Vencimento"}><input type="date" required {...input("due_date")} /></Field>
        <Field label="Forma de pagamento">
          <select {...input("payment_method")}>
            <option value="">—</option>
            {withValue(PAYMENT_METHODS, entry?.payment_method).map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </Field>
        {isNew && (
          <Field label="Repetir mensalmente por (meses)">
            <input type="number" min="1" max="60" required {...input("repeat_months")} />
          </Field>
        )}
        <Field label="Observações" span={2}><textarea rows={2} {...input("notes")} /></Field>
        {paid && <p className="muted span-2">Paga em {dateBR(entry.paid_at)} · {money(entry.paid_amount)}. Para mudar o valor, desfaça a baixa.</p>}

        {split && (
          <div className="span-2 form-grid">
            <Field label="Valor a separar (R$)">
              <input type="number" step="0.01" min="0.01" value={split.amount} onChange={(e) => setSplit({ ...split, amount: e.target.value })} />
            </Field>
            <Field label="Vencimento da nova parcela">
              <input type="date" value={split.due_date} onChange={(e) => setSplit({ ...split, due_date: e.target.value })} />
            </Field>
            <div className="actions span-2">
              <button type="button" className="btn" onClick={() => setSplit(null)}>Cancelar</button>
              <button type="button" className="btn btn-primary" disabled={busy || !split.amount}
                onClick={() => run(() => api.post(`/finance/entries/${entry.id}/split`, { amount: Number(split.amount), due_date: split.due_date }))}>
                Confirmar desmembramento
              </button>
            </div>
          </div>
        )}

        <div className="span-2"><ErrorBox msg={error} /></div>
        <div className="actions span-2">
          {!isNew && <button type="button" className="btn danger" onClick={remove}>Excluir</button>}
          {!isNew && !paid && !split && (
            <button type="button" className="btn" onClick={() => setSplit({ amount: "", due_date: addDays(entry.due_date, 30) })}>Desmembrar</button>
          )}
          {paid && <button type="button" className="btn" disabled={busy} onClick={() => run(() => api.post(`/finance/entries/${entry.id}/unpay`))}>Desfazer baixa</button>}
          <button className="btn btn-primary" disabled={busy}>{isNew ? "Lançar" : "Salvar"}</button>
        </div>
      </form>
      {confirmDialog}
    </Modal>
  );
}

// Same card shape as the Pedidos KPIs (label + icon, value, caption) plus a colored top edge per tone;
// `active` marks the card whose filter is on
function Card({ label, icon, tone, card, active, onClick }) {
  return (
    <div className={`kpi kpi-clickable kpi-tone tone-${tone} ${active ? "kpi-active" : ""}`} role="button" tabIndex={0}
      aria-pressed={active} onClick={onClick}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } }}>
      <div className="kpi-header"><span>{label}</span><span className={`kpi-icon icon-${tone}`} aria-hidden="true">{icon}</span></div>
      <strong>{money(card.total)}</strong>
      <span>{card.count} {card.count === 1 ? "lançamento" : "lançamentos"}</span>
    </div>
  );
}

export default function Finance({ kind }) {
  const receivable = kind === "receivable";
  const [filters, setFilters] = useState({ status: "open", start: "", end: "", search: "", category: "" });
  const [list, setList] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [paying, setPaying] = useState(null);
  const [editing, setEditing] = useState(null); // entry, or "new"

  function load() {
    setError("");
    const { status, start, end, search, category } = filters;
    api.get("/finance/entries", { params: { kind, status, search, category, start: start || undefined, end: end || undefined } })
      .then((r) => setList(r.data)).catch((e) => setError(errorMessage(e)));
    api.get("/finance/summary", { params: { kind } })
      .then((r) => setSummary(r.data)).catch((e) => setError(errorMessage(e)));
  }
  useEffect(() => { const t = setTimeout(load, filters.search ? 250 : 0); return () => clearTimeout(t); }, [kind, filters]);

  const setFilter = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });
  const show = (next) => setFilters({ ...filters, start: "", end: "", ...next });
  const today = localDate();
  const week = addDays(today, 7);
  const noDates = !filters.start && !filters.end;
  const done = () => { setPaying(null); setEditing(null); load(); };

  return (
    <div className="page">
      {/* Same header as the Vendas tab: title + tabs on the left, the period menu (by due date) on the right */}
      <header className="dashboard-header">
        <div>
          <h1>{receivable ? "Contas a receber" : "Contas a pagar"}</h1>
          <RevenueTabs />
        </div>
        <div className="header-actions">
          <PeriodPicker label="Vencimento" presets={DUE_PRESETS} value={{ start: filters.start, end: filters.end }}
            onChange={({ start, end }) => setFilters({ ...filters, start, end })} />
          <button className="btn btn-primary" onClick={() => setEditing("new")}>Lançar conta</button>
        </div>
      </header>
      <ErrorBox msg={error} />

      {summary && (
        <section className="orders-kpis finance-kpis">
          <Card label="Vencido" icon="⏰" tone="amber" card={summary.overdue}
            active={filters.status === "overdue" && noDates} onClick={() => show({ status: "overdue" })} />
          <Card label="Vence em 7 dias" icon="📅" tone="gold" card={summary.due_soon}
            active={filters.status === "open" && filters.start === today && filters.end === week}
            onClick={() => show({ status: "open", start: today, end: week })} />
          <Card label="Em aberto" icon="📋" tone="indigo" card={summary.open}
            active={filters.status === "open" && noDates} onClick={() => show({ status: "open" })} />
          <Card label={receivable ? "Recebido no mês" : "Pago no mês"} icon="✅" tone="teal" card={summary.paid_this_month}
            active={filters.status === "paid" && noDates} onClick={() => show({ status: "paid" })} />
        </section>
      )}

      {/* Same layout as the Pedidos filters: search, then the status chips (and the category, for payables) */}
      <div className="filter-bar">
        <input placeholder={receivable ? "Buscar por cliente ou descrição" : "Buscar por fornecedor ou descrição"}
          value={filters.search} onChange={setFilter("search")} />
        <div className="filter-group">
          <div className="period-chips" role="group" aria-label="Situação">
            {STATUS_FILTERS.map(([v, l]) => (
              <button key={v} type="button" className={`period-chip ${filters.status === v ? "on" : ""}`}
                onClick={() => setFilters({ ...filters, status: v })}>{l}</button>
            ))}
          </div>
          {!receivable && (
            <select value={filters.category} onChange={setFilter("category")} aria-label="Categoria">
              <option value="">Todas as categorias</option>
              {PAYABLE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          )}
        </div>
      </div>

      <section className="panel">
        {!list.length ? <EmptyState text="Nenhum lançamento encontrado." /> : (
          <table className="table">
            <thead>
              <tr>
                <th>Vencimento</th><th>{receivable ? "Cliente" : "Fornecedor"}</th><th>{receivable ? "Pedido" : "Categoria"}</th>
                <th>Descrição</th><th>Parcela</th><th className="num">Valor</th><th>Situação</th><th></th>
              </tr>
            </thead>
            <tbody>
              {list.map((x) => (
                <tr key={x.id} className={`clickable ${x.status === "overdue" ? "row-overdue" : ""}`} onClick={() => setEditing(x)}>
                  <td>{dateBR(x.due_date)}</td>
                  <td>{(receivable ? x.customer_name : x.supplier) || "—"}</td>
                  <td>{receivable
                    ? (x.order_id ? <Link to={`/orders/${x.order_id}`} onClick={(e) => e.stopPropagation()}>{orderNumber(x.order_id)}</Link> : "—")
                    : x.category}</td>
                  <td>{x.description}</td>
                  <td>{x.installments ? `${x.installment}/${x.installments}` : "—"}</td>
                  <td className="num">{money(x.amount)}</td>
                  <td><EntryStatus s={x.status} /></td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {x.paid_at
                      ? <span className="muted">pago em {dateBR(x.paid_at)}</span>
                      : <button className="btn btn-light" onClick={() => setPaying(x)}>Dar baixa</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {paying && <PayModal entry={paying} onClose={() => setPaying(null)} onDone={done} />}
      {editing && <EntryModal kind={kind} entry={editing === "new" ? null : editing} onClose={() => setEditing(null)} onDone={done} />}
    </div>
  );
}

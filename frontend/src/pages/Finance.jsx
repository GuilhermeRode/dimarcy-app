import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import { addDays, dateBR, localDate, money, orderNumber } from "../format";
import { EmptyState, ErrorBox, Field, Modal, useConfirm } from "../components/ui";
import { RevenueHeader } from "../components/RevenueTabs";
import PeriodPicker from "../components/PeriodPicker";
import { useSort } from "../components/useSort";

// Same list as PAYABLE_CATEGORIES in backend/app/models.py
const PAYABLE_CATEGORIES = ["Matéria-prima", "Aluguel", "Salários", "Impostos", "Energia", "Manutenção", "Outros"];
const PAYMENT_METHODS = ["Boleto", "Pix", "Transferência", "Cheque", "Dinheiro", "Cartão"];
const STATUS_RANK = { overdue: 0, open: 1, paid: 2 }; // sort order of the Situação column
const EMPTY_FILTERS = { status: "open", start: "", end: "", search: "", category: "" };
// Due-date periods look ahead (unlike the sales ones); "Todos" = no date filter
const monthEnd = () => { const d = new Date(); return localDate(new Date(d.getFullYear(), d.getMonth() + 1, 0)); };
const DUE_PRESETS = [
  { key: "all", label: "Todos", start: () => "", end: () => "" },
  { key: "7d", label: "7 dias", start: localDate, end: () => addDays(localDate(), 7) },
  { key: "month", label: "Este mês", start: () => `${localDate().slice(0, 8)}01`, end: monthEnd },
];

const DAY_MS = 86400000;
const daysUntil = (iso, today) => Math.round((Date.parse(iso) - Date.parse(today)) / DAY_MS); // ISO dates parse as UTC
const days = (n) => `${n} ${n === 1 ? "dia" : "dias"}`;
const MONTH_FMT = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" });
const monthLabel = (ym) => {
  const s = MONTH_FMT.format(new Date(`${ym}-01T00:00:00`)).replace(" de ", " "); // "outubro 2026"
  return s.charAt(0).toUpperCase() + s.slice(1);
};

// Situação badge: how late, how soon, or when it was paid
export function EntryStatus({ entry, today = localDate() }) {
  if (entry.paid_at) return <span className="badge badge-paid">Paga em {dateBR(entry.paid_at).slice(0, 5)}</span>;
  const d = daysUntil(entry.due_date, today);
  if (d < 0) return <span className="badge badge-overdue">Vencida há {days(-d)}</span>;
  if (d === 0) return <span className="badge badge-soon">Vence hoje</span>;
  if (d <= 7) return <span className="badge badge-soon">Vence em {days(d)}</span>;
  return <span className="badge badge-open">Em aberto</span>;
}

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

// Pays several open entries at once, each for its full amount, on the same date
function BulkPayModal({ entries, onClose, onDone }) {
  const [f, setF] = useState({ paid_at: localDate(), payment_method: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const total = entries.reduce((sum, x) => sum + x.amount, 0);

  async function save(e) {
    e.preventDefault();
    setError(""); setBusy(true);
    for (const x of entries) {
      try {
        await api.post(`/finance/entries/${x.id}/pay`, { paid_at: f.paid_at, payment_method: f.payment_method || null });
      } catch (err) {
        setError(`${x.description}: ${errorMessage(err)}`); // the ones before it are already paid; closing reloads the list
        setBusy(false);
        return;
      }
    }
    onDone();
  }

  return (
    <Modal title={`Dar baixa em ${entries.length} ${entries.length === 1 ? "lançamento" : "lançamentos"}`} onClose={onClose}>
      <form onSubmit={save} className="form-grid">
        <p className="span-2" style={{ margin: 0 }}>Total: <strong>{money(total)}</strong> · cada um pelo valor integral.</p>
        <Field label="Data do pagamento">
          <input type="date" required value={f.paid_at} onChange={(e) => setF({ ...f, paid_at: e.target.value })} />
        </Field>
        <Field label="Forma de pagamento">
          <select value={f.payment_method} onChange={(e) => setF({ ...f, payment_method: e.target.value })}>
            <option value="">Manter a de cada lançamento</option>
            {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </Field>
        <div className="span-2"><ErrorBox msg={error} /></div>
        <div className="actions span-2"><button className="btn btn-primary" disabled={busy}>Confirmar baixa</button></div>
      </form>
    </Modal>
  );
}

// Reads a CSV/XLSX on the server, shows what it understood, and only then creates the entries
function ImportModal({ kind, onClose, onDone }) {
  const payable = kind === "payable";
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null); // { entries, items, errors }
  const [card, setCard] = useState(null); // { card_due, card_name, category } while importing a card statement
  const [mode, setModeState] = useState("list"); // "list" | "card" | "boleto"
  const [bol, setBol] = useState(null); // the boleto read, plus what the user types: supplier, description, category
  const [code, setCode] = useState(""); // pasted linha digitável
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(f, apply, c = card) {
    if (!f || (c && !c.card_due)) return;
    const fd = new FormData();
    fd.append("file", f);
    setError(""); setBusy(true);
    try {
      const { data } = await api.post("/finance/import", fd, { params: { kind, apply, ...c } });
      if (apply) return onDone();
      setPreview(data);
    } catch (err) { setError(errorMessage(err)); }
    setBusy(false);
  }

  const [over, setOver] = useState(false); // a file is being dragged over the drop zone

  // Value and due date from the boleto's PDF or its linha digitável; the user completes the rest
  async function readBoleto(key, value) {
    const fd = new FormData();
    fd.append(key, value);
    setError(""); setBusy(true);
    try {
      const { data } = await api.post("/finance/boleto", fd);
      setBol((cur) => ({ supplier: "", description: "Boleto", category: "Outros", ...cur,
        code: data.code, amount: data.amount ?? "", due_date: data.due_date ?? "" }));
      setCode(data.code);
    } catch (err) { setError(errorMessage(err)); }
    setBusy(false);
  }

  async function saveBoleto() {
    setError(""); setBusy(true);
    try {
      await api.post("/finance/entries", {
        kind, description: bol.description, amount: Number(bol.amount), due_date: bol.due_date, payment_method: "Boleto",
        notes: `Linha digitável: ${bol.code}`, supplier: bol.supplier || null, category: bol.category,
      });
      onDone();
    } catch (err) { setError(errorMessage(err)); setBusy(false); }
  }

  function choose(f) {
    setOver(false);
    if (!f) return;
    if (payable && mode !== "card" && /\.pdf$/i.test(f.name)) {  // a PDF dropped on "Lista de contas" is a boleto too
      setModeState("boleto"); setFile(f); setPreview(null);
      return readBoleto("file", f);
    }
    if (mode === "boleto") return setError("Envie o boleto em PDF.");
    if (!/\.(csv|xlsx|txt)$/i.test(f.name)) {
      setFile(null); setPreview(null);
      return setError("Envie um arquivo .csv ou .xlsx.");
    }
    setFile(f); setPreview(null);
    send(f, false);
  }

  // Changing a card field reads the file again, so the preview always matches what will be saved
  function setCardField(k, v) {
    const next = card ? { ...card, [k]: v } : null;
    setCard(next); setPreview(null);
    send(file, false, next);
  }

  function setMode(m) {
    if (m === mode) return;
    const next = m === "card" ? { card_due: "", card_name: "", category: "Outros" } : null;
    setModeState(m); setCard(next); setPreview(null); setError("");
    if (m === "boleto" || mode === "boleto") { setFile(null); setBol(null); setCode(""); return; }
    send(file, false, next);
  }

  const entries = preview?.entries || [];
  const items = preview?.items || [];
  const errors = preview?.errors || [];
  const total = entries.reduce((sum, x) => sum + x.amount, 0);
  let status = "";
  if (busy) status = "Lendo o arquivo…";
  else if (mode === "boleto") status = bol ? "Boleto lido — confira e complete abaixo" : "";
  else if (card && file && !card.card_due) status = "Informe o vencimento da fatura para ver a prévia";
  else if (errors.length) status = `${errors.length} ${errors.length === 1 ? "problema encontrado" : "problemas encontrados"}`;
  else if (entries.length) status = `${entries.length} ${entries.length === 1 ? "lançamento pronto" : "lançamentos prontos"} para importar`;

  return (
    <Modal title={payable ? "Importar contas a pagar" : "Importar contas a receber"} onClose={onClose} wide>
      <div className="import">
        {payable && (
          <div className="segmented import-mode" role="group" aria-label="Tipo de arquivo">
            {[["list", "Lista de contas"], ["card", "Fatura de cartão"], ["boleto", "Boleto (PDF)"]].map(([m, label]) => (
              <button key={m} type="button" className={mode === m ? "on" : ""} aria-pressed={mode === m} onClick={() => setMode(m)}>{label}</button>
            ))}
          </div>
        )}

        {card && (
          <div className="import-card">
            <Field label="Cartão"><input maxLength={120} placeholder="Ex.: Nubank" value={card.card_name}
              onChange={(e) => setCard({ ...card, card_name: e.target.value })} onBlur={(e) => setCardField("card_name", e.target.value)} /></Field>
            <Field label="Vencimento da fatura">
              <input type="date" required value={card.card_due} onChange={(e) => setCardField("card_due", e.target.value)} />
            </Field>
            <Field label="Categoria">
              <select value={card.category} onChange={(e) => setCardField("category", e.target.value)}>
                {PAYABLE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </Field>
          </div>
        )}

        <label className={`dropzone ${over ? "drop-over" : ""} ${file ? "has-file" : ""}`}
          onDragOver={(e) => { e.preventDefault(); if (!over) setOver(true); }}
          onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOver(false); }}
          onDrop={(e) => { e.preventDefault(); choose(e.dataTransfer.files[0]); }}>
          <input type="file" accept={mode === "boleto" ? ".pdf" : payable && !card ? ".csv,.xlsx,.txt,.pdf" : ".csv,.xlsx,.txt"} hidden disabled={busy}
            onChange={(e) => { choose(e.target.files[0]); e.target.value = ""; }} />
          <svg className="dropzone-icon" viewBox="0 0 24 24" aria-hidden="true">
            {file
              ? <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zm0 0v5h5M9 13h6M9 17h6" />
              : <path d="M12 16V4m0 0L7 9m5-5 5 5M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />}
          </svg>
          {file ? (
            <span className="dropzone-text">
              <strong>{file.name}</strong>
              <span className={errors.length && !busy ? "dropzone-bad" : "muted"}>{status || `${Math.max(1, Math.round(file.size / 1024))} KB`}</span>
              <span className="dropzone-link">Trocar arquivo</span>
            </span>
          ) : (
            <span className="dropzone-text">
              <strong>{over ? "Solte o arquivo aqui" : mode === "boleto" ? "Arraste o PDF do boleto para cá" : "Arraste o arquivo para cá"}</strong>
              <span className="muted">ou <span className="dropzone-link">clique para escolher</span> · {mode === "boleto" ? "PDF" : "CSV ou XLSX"}, até 5 MB</span>
            </span>
          )}
        </label>

        {mode === "boleto" && (
          <div className="field-row">
            <input style={{ flex: 1 }} inputMode="numeric" aria-label="Linha digitável" placeholder="Ou cole a linha digitável"
              value={code} onChange={(e) => setCode(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (code.trim()) readBoleto("code", code); } }} />
            <button type="button" className="btn" disabled={!code.trim() || busy} onClick={() => readBoleto("code", code)}>Ler</button>
          </div>
        )}

        {mode === "boleto" && bol && (
          <div className="import-preview">
            <div className="import-preview-head">
              <strong>Boleto</strong>
              <span className="muted boleto-code">{bol.code}</span>
            </div>
            <div className="form-grid boleto-form">
              <Field label="Fornecedor / favorecido"><input maxLength={160} autoFocus value={bol.supplier}
                onChange={(e) => setBol({ ...bol, supplier: e.target.value })} /></Field>
              <Field label="Categoria">
                <select value={bol.category} onChange={(e) => setBol({ ...bol, category: e.target.value })}>
                  {PAYABLE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </Field>
              <Field label="Descrição" span={2}><input required maxLength={200} value={bol.description}
                onChange={(e) => setBol({ ...bol, description: e.target.value })} /></Field>
              <Field label="Valor (R$)"><input type="number" step="0.01" min="0.01" required value={bol.amount}
                onChange={(e) => setBol({ ...bol, amount: e.target.value })} /></Field>
              <Field label="Vencimento"><input type="date" required value={bol.due_date}
                onChange={(e) => setBol({ ...bol, due_date: e.target.value })} /></Field>
              {!bol.due_date && <p className="dropzone-bad span-2">Este boleto não traz o vencimento no código — informe a data.</p>}
            </div>
          </div>
        )}

        <details className="import-help">
          <summary>{mode === "boleto" ? "Que boleto funciona?" : "Como a planilha precisa estar?"}</summary>
          {mode === "boleto" ? (
            <p>O PDF do boleto como o banco ou o fornecedor envia: o valor e o vencimento são lidos da linha digitável e conferidos pelos
              dígitos verificadores. Boleto escaneado ou foto não tem texto para ler — nesse caso, cole a linha digitável. Contas de
              luz, água e impostos nem sempre trazem o vencimento no código.</p>
          ) : card ? (
            <p>A fatura exportada do banco, com uma linha por compra e a coluna <strong>Valor</strong> (Data e Descrição são opcionais).
              Vira uma conta só com o total; o pagamento da fatura anterior é ignorado e as compras ficam nas observações.</p>
          ) : (
            <p>Uma linha por lançamento, com as colunas <strong>Valor</strong> e <strong>Vencimento</strong>. Opcionais: Descrição,{" "}
              {payable ? "Fornecedor, Categoria" : "Cliente"}, Forma de pagamento, Observações e Pago em (já entra com baixa).
              Pode ter um título acima do cabeçalho.</p>
          )}
        </details>

        {errors.length > 0 && (
          <div className="import-errors" role="alert">
            <strong>Corrija a planilha e envie de novo — nada foi importado.</strong>
            <ul>{errors.map((x) => <li key={x}>{x}</li>)}</ul>
          </div>
        )}

        {entries.length > 0 && (
          <div className="import-preview">
            <div className="import-preview-head">
              <strong>Prévia</strong>
              <span className="muted">{entries.length} {entries.length === 1 ? "lançamento" : "lançamentos"} · <strong>{money(total)}</strong></span>
            </div>
            <div className="table-scroll">
              <table className="table">
                <thead>
                  <tr>
                    <th>Vencimento</th><th>{payable ? "Fornecedor · Descrição" : "Descrição"}</th>
                    {payable && <th>Categoria</th>}<th className="num">Valor</th><th>Situação</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((x, i) => (
                    <tr key={i}>
                      <td>{dateBR(x.due_date)}</td>
                      <td>
                        <span className="cell-stack">
                          <strong className="cell-main">{(payable && x.supplier) || x.description}</strong>
                          {payable && x.supplier && <span className="cell-sub">{x.description}</span>}
                        </span>
                      </td>
                      {payable && <td><span className="cat-tag">{x.category}</span></td>}
                      <td className="num"><strong>{money(x.amount)}</strong></td>
                      <td>{x.paid_at
                        ? <span className="badge badge-paid">Paga em {dateBR(x.paid_at).slice(0, 5)}</span>
                        : <span className="badge badge-open">Em aberto</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {items.length > 0 && (
              <details className="import-items">
                <summary>Ver as {items.length} {items.length === 1 ? "compra" : "compras"} da fatura</summary>
                <table className="table">
                  <tbody>
                    {items.map((x, i) => (
                      <tr key={i}>
                        <td className="muted">{x.date ? dateBR(x.date) : "—"}</td><td>{x.description}</td>
                        <td className="num">{money(x.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            )}
          </div>
        )}

        <ErrorBox msg={error} />
        <div className="actions">
          <button type="button" className="btn" onClick={onClose}>Cancelar</button>
          {mode === "boleto" ? (
            <button type="button" className="btn btn-primary" onClick={saveBoleto}
              disabled={busy || !bol || !(Number(bol.amount) > 0) || !bol.due_date || !bol.description.trim()}>Lançar boleto</button>
          ) : (
            <button type="button" className="btn btn-primary" disabled={busy || !entries.length || errors.length > 0} onClick={() => send(file, true)}>
              {entries.length ? `Importar ${entries.length} ${entries.length === 1 ? "lançamento" : "lançamentos"}` : "Importar"}
            </button>
          )}
        </div>
      </div>
    </Modal>
  );
}

// Colored dot + label, value, caption; `active` marks the card whose filter is on
function Card({ label, tone, card, active, onClick }) {
  return (
    <div className={`kpi kpi-clickable fin-card ${active ? "kpi-active" : ""}`} role="button" tabIndex={0}
      aria-pressed={active} onClick={onClick}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } }}>
      <span className="fin-card-label"><i className={`dot dot-${tone}`} aria-hidden="true" />{label}</span>
      <strong className={tone === "red" ? "value-danger" : ""}>{money(card.total)}</strong>
      <span className="muted">{card.count} {card.count === 1 ? "lançamento" : "lançamentos"}</span>
    </div>
  );
}

export default function Finance({ kind }) {
  const receivable = kind === "receivable";
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [list, setList] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(() => new Set()); // ids ticked for a bulk "Dar baixa"
  const [paying, setPaying] = useState(null);
  const [bulkPaying, setBulkPaying] = useState(false);
  const [editing, setEditing] = useState(null); // entry, or "new"
  const [importing, setImporting] = useState(false);

  function load() {
    setError("");
    const { status, start, end, search, category } = filters;
    api.get("/finance/entries", { params: { kind, status, search, category, start: start || undefined, end: end || undefined } })
      .then((r) => { setList(r.data); setSelected(new Set()); }).catch((e) => setError(errorMessage(e)));
    api.get("/finance/summary", { params: { kind } })
      .then((r) => setSummary(r.data)).catch((e) => setError(errorMessage(e)));
  }
  useEffect(() => { const t = setTimeout(load, filters.search ? 250 : 0); return () => clearTimeout(t); }, [kind, filters]);

  const { sorted, sort, sortHeader } = useSort(list, {
    due: (x) => x.due_date,
    party: (x) => (receivable ? x.customer_name : x.supplier) || x.description,
    ref: (x) => (receivable ? x.order_id : x.category),
    installment: (x) => x.installment,
    amount: (x) => x.amount,
    status: (x) => STATUS_RANK[x.status],
  }, { key: "due", dir: 1 });

  const setFilter = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });
  const show = (next) => setFilters({ ...filters, start: "", end: "", ...next });
  const today = localDate();
  const week = addDays(today, 7);
  const noDates = !filters.start && !filters.end;
  const filtersOn = filters.search || filters.category || !noDates || filters.status !== "open";
  const total = list.reduce((sum, x) => sum + x.amount, 0);
  const open = sorted.filter((x) => !x.paid_at);
  const picked = sorted.filter((x) => selected.has(x.id));
  const allPicked = open.length > 0 && open.every((x) => selected.has(x.id));
  const toggle = (id) => setSelected((cur) => {
    const next = new Set(cur);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const done = () => { setPaying(null); setBulkPaying(false); setEditing(null); setImporting(false); load(); };
  const noun = receivable ? ["parcela", "parcelas"] : ["conta", "contas"];

  // Month group headers only make sense while the list is in due-date order
  const rows = [];
  let month = null;
  for (const x of sorted) {
    const m = x.due_date.slice(0, 7);
    if (sort?.key === "due" && m !== month) {
      month = m;
      const items = sorted.filter((y) => y.due_date.slice(0, 7) === m);
      rows.push(
        <tr key={`month-${m}`} className="group-row">
          <td colSpan={8}>
            <div>
              <strong>{monthLabel(m)}</strong>
              <span className="muted">
                {items.length} {items.length === 1 ? noun[0] : noun[1]} · <strong>{money(items.reduce((sum, y) => sum + y.amount, 0))}</strong>
              </span>
            </div>
          </td>
        </tr>,
      );
    }
    const party = receivable ? x.customer_name : x.supplier;
    rows.push(
      <tr key={x.id} className={`clickable ${selected.has(x.id) ? "row-selected" : ""}`} onClick={() => setEditing(x)}>
        <td className="cell-check" onClick={(e) => e.stopPropagation()}>
          <input type="checkbox" disabled={Boolean(x.paid_at)} checked={selected.has(x.id)} onChange={() => toggle(x.id)}
            aria-label={`Selecionar ${x.description}`} />
        </td>
        <td className={x.status === "overdue" ? "due-overdue" : ""}>{dateBR(x.due_date)}</td>
        <td>
          <span className="cell-stack">
            <strong className="cell-main">{party || x.description}</strong>
            {party && <span className="cell-sub">{x.description}</span>}
          </span>
        </td>
        <td>{receivable
          ? (x.order_id ? <Link className="ref" to={`/orders/${x.order_id}`} state={{ back: { to: "/revenue/receivables", label: "Contas a receber" } }} onClick={(e) => e.stopPropagation()}>{orderNumber(x.order_id)}</Link> : "—")
          : <span className="cat-tag">{x.category}</span>}</td>
        <td className="muted">{x.installments ? `${x.installment}/${x.installments}` : "—"}</td>
        <td className="num"><strong>{money(x.amount)}</strong></td>
        <td><EntryStatus entry={x} today={today} /></td>
        <td className="num" onClick={(e) => e.stopPropagation()}>
          {!x.paid_at && <button className="btn btn-light" onClick={() => setPaying(x)}>Dar baixa</button>}
        </td>
      </tr>,
    );
  }

  return (
    <div className="page">
      <RevenueHeader subtitle={receivable ? "Acompanhe os recebimentos dos clientes e dê baixa no que entrou."
        : "Controle as contas da empresa e dê baixa no que foi pago."}>
        <PeriodPicker presets={DUE_PRESETS} value={{ start: filters.start, end: filters.end }}
          onChange={({ start, end }) => setFilters({ ...filters, start, end })} />
        <button className="btn" onClick={() => setImporting(true)}>Importar arquivo</button>
        <button className="btn btn-primary" onClick={() => setEditing("new")}>+ Lançar conta</button>
      </RevenueHeader>
      <ErrorBox msg={error} />

      {summary && (
        <section className="orders-kpis finance-kpis">
          <Card label="Vencido" tone="red" card={summary.overdue}
            active={filters.status === "overdue" && noDates} onClick={() => show({ status: "overdue" })} />
          <Card label="Vence em 7 dias" tone="amber" card={summary.due_soon}
            active={filters.status === "open" && filters.start === today && filters.end === week}
            onClick={() => show({ status: "open", start: today, end: week })} />
          <Card label="Em aberto" tone="blue" card={summary.open}
            active={filters.status === "open" && noDates} onClick={() => show({ status: "open" })} />
          <Card label={receivable ? "Recebido no mês" : "Pago no mês"} tone="green" card={summary.paid_this_month}
            active={filters.status === "paid" && noDates} onClick={() => show({ status: "paid" })} />
        </section>
      )}

      <section className="panel panel-table">
        <div className="table-toolbar">
          <input className="toolbar-search" value={filters.search} onChange={setFilter("search")}
            placeholder={receivable ? "Buscar por cliente ou descrição" : "Buscar por fornecedor ou descrição"} />
          {!receivable && (
            <select value={filters.category} onChange={setFilter("category")} aria-label="Categoria">
              <option value="">Todas as categorias</option>
              {PAYABLE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          )}
          {filtersOn && <button type="button" className="link-btn" onClick={() => setFilters(EMPTY_FILTERS)}>Limpar filtros</button>}
          <span className="muted toolbar-summary">
            {list.length} {list.length === 1 ? "lançamento" : "lançamentos"} · {money(total)}
          </span>
        </div>

        {!list.length ? <EmptyState text="Nenhum lançamento encontrado." /> : (
          <div className="table-scroll">
            <table className="table table-fin">
              <thead>
                <tr>
                  <th className="cell-check">
                    <input type="checkbox" checked={allPicked} disabled={!open.length} aria-label="Selecionar todos em aberto"
                      onChange={() => setSelected(allPicked ? new Set() : new Set(open.map((x) => x.id)))} />
                  </th>
                  {sortHeader("due", "Vencimento")}
                  {sortHeader("party", receivable ? "Cliente · Descrição" : "Fornecedor · Descrição")}
                  {sortHeader("ref", receivable ? "Pedido" : "Categoria")}
                  {sortHeader("installment", "Parcela")}
                  {sortHeader("amount", "Valor", "num")}
                  {sortHeader("status", "Situação")}
                  <th></th>
                </tr>
              </thead>
              <tbody>{rows}</tbody>
            </table>
          </div>
        )}
      </section>

      {picked.length > 0 && <div className="bulk-spacer" />}{/* keeps the last rows reachable above the bar */}
      {picked.length > 0 && (
        <div className="bulk-bar" role="region" aria-label="Seleção">
          <strong>{picked.length} {picked.length === 1 ? "selecionado" : "selecionados"}</strong>
          <span>{money(picked.reduce((sum, x) => sum + x.amount, 0))}</span>
          <button className="btn btn-primary" onClick={() => setBulkPaying(true)}>Dar baixa nos selecionados</button>
          <button type="button" className="link-btn" onClick={() => setSelected(new Set())}>Limpar</button>
        </div>
      )}

      {paying && <PayModal entry={paying} onClose={() => setPaying(null)} onDone={done} />}
      {bulkPaying && <BulkPayModal entries={picked} onClose={done} onDone={done} />}
      {importing && <ImportModal kind={kind} onClose={() => setImporting(false)} onDone={done} />}
      {editing && <EntryModal kind={kind} entry={editing === "new" ? null : editing} onClose={() => setEditing(null)} onDone={done} />}
    </div>
  );
}

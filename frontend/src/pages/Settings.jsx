import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { ErrorBox, Field } from "../components/ui";

const LEAD_SIZES = [["01", "ME"], ["03", "EPP"], ["05", "Grande"], ["00", "Não informado"]];

export default function Settings() {
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/settings").then((r) => setForm(r.data)).catch((e) => setError(errorMessage(e)));
  }, []);

  function toggleSize(code) {
    const current = (form.lead_sizes || "").split(",").filter(Boolean);
    const next = current.includes(code) ? current.filter((c) => c !== code) : [...current, code];
    setForm({ ...form, lead_sizes: next.join(",") });
  }

  async function save(e) {
    e.preventDefault();
    setError(""); setOk(""); setBusy(true);
    try {
      const { data } = await api.put("/settings", {
        allow_price_override: form.allow_price_override,
        max_discount_percent: Number(form.max_discount_percent) || 0,
        retail_markup_percent: Number(form.retail_markup_percent) || 0,
        annual_goal: form.annual_goal === "" || form.annual_goal == null ? null : Number(form.annual_goal),
        lead_cnaes: form.lead_cnaes,
        lead_sizes: form.lead_sizes,
        lead_exclude_mei: form.lead_exclude_mei,
        lead_head_office_only: form.lead_head_office_only,
        lead_require_contact: form.lead_require_contact,
        lead_min_age_months: Number(form.lead_min_age_months) || 0,
        lead_states: form.lead_states,
        lead_weekly_release: Number(form.lead_weekly_release) || 0,
      });
      setForm(data);
      setOk("Configurações salvas com sucesso.");
    } catch (err) {
      setError(errorMessage(err));
    } finally { setBusy(false); }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Configurações</h1>
        <p className="muted">Regras de preço, desconto, meta de vendas e prospecção.</p>
      </header>

      {form ? (
        <form onSubmit={save} className="page">
          <section className="panel">
            <h3>Preços</h3>
            <div className="form-grid">
              <label className="switch-row span-2">
                <span>
                  Administradores podem alterar o preço no pedido
                  <small className="muted">Vendedores nunca alteram. Desligado, o preço vem sempre do cadastro do produto.</small>
                </span>
                <input type="checkbox" role="switch" className="switch" checked={form.allow_price_override}
                  onChange={(e) => setForm({ ...form, allow_price_override: e.target.checked })} />
              </label>
              <Field label="Acréscimo da tabela de varejo (%)" span={2}>
                <input type="number" min="0" max="1000" step="0.01" value={form.retail_markup_percent}
                  onChange={(e) => setForm({ ...form, retail_markup_percent: e.target.value })} />
                <small className="muted">Somado ao preço de atacado. A tabela de cada vendedor é definida em Usuários.</small>
              </Field>
            </div>
          </section>

          <section className="panel">
            <h3>Desconto</h3>
            <div className="form-grid">
              <Field label="Desconto máximo por pedido (%)" span={2}>
                <input type="number" min="0" max="100" step="0.01" value={form.max_discount_percent}
                  onChange={(e) => setForm({ ...form, max_discount_percent: e.target.value })} />
              </Field>
            </div>
          </section>

          <section className="panel">
            <h3>Meta de vendas</h3>
            <div className="form-grid">
              <Field label="Meta anual da empresa (R$)" span={2}>
                <input type="number" min="0" step="0.01" placeholder="Sem meta"
                  value={form.annual_goal ?? ""}
                  onChange={(e) => setForm({ ...form, annual_goal: e.target.value })} />
                <small className="muted">O ano da meta vai de outubro a setembro. As metas dos vendedores ficam em Usuários.</small>
              </Field>
            </div>
          </section>

          <section className="panel">
            <h3>Prospecção</h3>
            <div className="form-grid">
              <Field label="Estados da prospecção" span={2}>
                <input placeholder="PR, RS, SC" value={form.lead_states || ""}
                  onChange={(e) => setForm({ ...form, lead_states: e.target.value })} />
                <small className="muted">Siglas separadas por vírgula. A importação traz as lojas desses estados.</small>
              </Field>
              <Field label="CNAEs da prospecção" span={2}>
                <input placeholder="4781-4/00" value={form.lead_cnaes || ""}
                  onChange={(e) => setForm({ ...form, lead_cnaes: e.target.value })} />
                <small className="muted">Atividade principal das lojas trazidas da Receita Federal (separe por vírgula). Padrão: 4781-4/00, comércio varejista de artigos do vestuário e acessórios.</small>
              </Field>
              <div className="span-2">
                <span>Porte da empresa</span>
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 6 }}>
                  {LEAD_SIZES.map(([code, label]) => (
                    <label className="check" key={code}>
                      <input type="checkbox" checked={(form.lead_sizes || "").split(",").includes(code)}
                        onChange={() => toggleSize(code)} />
                      {label}
                    </label>
                  ))}
                </div>
              </div>
              <label className="switch-row span-2">
                <span>Excluir MEI</span>
                <input type="checkbox" role="switch" className="switch" checked={form.lead_exclude_mei}
                  onChange={(e) => setForm({ ...form, lead_exclude_mei: e.target.checked })} />
              </label>
              <label className="switch-row span-2">
                <span>Só a matriz (sem filiais)</span>
                <input type="checkbox" role="switch" className="switch" checked={form.lead_head_office_only}
                  onChange={(e) => setForm({ ...form, lead_head_office_only: e.target.checked })} />
              </label>
              <label className="switch-row span-2">
                <span>Só lojas com telefone</span>
                <input type="checkbox" role="switch" className="switch" checked={form.lead_require_contact}
                  onChange={(e) => setForm({ ...form, lead_require_contact: e.target.checked })} />
              </label>
              <Field label="Abertas há pelo menos (meses)" span={2}>
                <input type="number" min="0" max="120" step="1" value={form.lead_min_age_months ?? ""}
                  onChange={(e) => setForm({ ...form, lead_min_age_months: e.target.value })} />
                <small className="muted">Mudar um filtro faz a próxima importação buscar as lojas de novo.</small>
              </Field>
              <Field label="Liberar por vendedor, por semana" span={2}>
                <input type="number" min="0" max="500" step="1" value={form.lead_weekly_release ?? ""}
                  onChange={(e) => setForm({ ...form, lead_weekly_release: e.target.value })} />
                <small className="muted">
                  Toda madrugada o sistema completa esse número com as melhores lojas da região de cada vendedor
                  (celular, sem dívida ativa, maior capital social, aberta há até 5 anos, cidade onde já vendemos).
                  Lojas com dívida ou capital baixo não são excluídas, só vão para o fim da fila. 0 desliga.
                </small>
              </Field>
            </div>
          </section>

          <ErrorBox msg={error} />
          {ok && <div className="muted">{ok}</div>}
          <div className="actions">
            <button className="btn btn-primary" disabled={busy}>Salvar configurações</button>
          </div>
        </form>
      ) : <ErrorBox msg={error} />}
    </div>
  );
}

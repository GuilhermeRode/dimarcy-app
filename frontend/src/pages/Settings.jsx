import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { ErrorBox, Field } from "../components/ui";

export default function Settings() {
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/settings").then((r) => setForm(r.data)).catch((e) => setError(errorMessage(e)));
  }, []);

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
        <p className="muted">Regras de preço, desconto e meta de vendas.</p>
      </header>

      {form ? (
        <section className="panel">
          <form onSubmit={save} className="form-grid">
            <div className="span-2">
              <label className="check">
                <input type="checkbox" checked={form.allow_price_override}
                  onChange={(e) => setForm({ ...form, allow_price_override: e.target.checked })} />
                Permitir que administradores alterem o preço unitário no pedido
              </label>
              <p className="muted" style={{ marginTop: 4 }}>
                Vendedores nunca alteram o preço. Quando desligado, o preço sempre vem do cadastro do produto.
              </p>
            </div>
            <Field label="Desconto máximo por pedido (%)" span={2}>
              <input type="number" min="0" max="100" step="0.01" value={form.max_discount_percent}
                onChange={(e) => setForm({ ...form, max_discount_percent: e.target.value })} />
            </Field>
            <Field label="Acréscimo da tabela de varejo (%)" span={2}>
              <input type="number" min="0" max="1000" step="0.01" value={form.retail_markup_percent}
                onChange={(e) => setForm({ ...form, retail_markup_percent: e.target.value })} />
            </Field>
            <p className="muted span-2" style={{ marginTop: -8 }}>
              Aplicado sobre o preço de atacado nos pedidos de varejo. A tabela de cada vendedor é definida em Usuários.
            </p>
            <Field label="Meta anual da empresa (R$)" span={2}>
              <input type="number" min="0" step="0.01" placeholder="Sem meta"
                value={form.annual_goal ?? ""}
                onChange={(e) => setForm({ ...form, annual_goal: e.target.value })} />
            </Field>
            <p className="muted span-2" style={{ marginTop: -8 }}>
              O ano da meta vai de outubro a setembro (a meta de 2027 vale de 01/10/2026 a 30/09/2027). No Painel e no Faturamento ela é proporcional ao período escolhido. Deixe em branco para não usar meta.
            </p>
            <Field label="CNAEs da prospecção" span={2}>
              <input placeholder="4781-4/00" value={form.lead_cnaes || ""}
                onChange={(e) => setForm({ ...form, lead_cnaes: e.target.value })} />
            </Field>
            <p className="muted span-2" style={{ marginTop: -8 }}>
              Atividade principal das lojas trazidas da Receita Federal (separe por vírgula). Padrão: 4781-4/00,
              comércio varejista de artigos do vestuário e acessórios.{" "}
              {form.last_lead_import_at
                ? `Última importação: dados de ${new Date(`${form.last_lead_import_month}-01T00:00:00`).toLocaleDateString("pt-BR", { month: "long", year: "numeric" })}, em ${new Date(`${form.last_lead_import_at}Z`).toLocaleDateString("pt-BR")}.`
                : "Ainda não houve importação."}
            </p>
            <div className="span-2"><ErrorBox msg={error} /></div>
            {ok && <div className="span-2 muted">{ok}</div>}
            <div className="actions span-2">
              <button className="btn btn-primary" disabled={busy}>Salvar configurações</button>
            </div>
          </form>
        </section>
      ) : <ErrorBox msg={error} />}
    </div>
  );
}

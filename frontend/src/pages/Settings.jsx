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

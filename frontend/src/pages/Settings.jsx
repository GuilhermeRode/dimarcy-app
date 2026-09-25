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
        <p className="muted">Regras de preço e desconto para o formulário de pedido.</p>
      </header>

      {form ? (
        <section className="panel">
          <form onSubmit={save} className="form-grid">
            <div className="span-2">
              <label className="check">
                <input type="checkbox" checked={form.allow_price_override}
                  onChange={(e) => setForm({ ...form, allow_price_override: e.target.checked })} />
                Permitir alterar o preço unitário no pedido
              </label>
              <p className="muted" style={{ marginTop: 4 }}>
                Quando desligado, o preço sempre vem do cadastro do produto.
              </p>
            </div>
            <Field label="Desconto máximo por pedido (%)" span={2}>
              <input type="number" min="0" max="100" step="0.01" value={form.max_discount_percent}
                onChange={(e) => setForm({ ...form, max_discount_percent: e.target.value })} />
            </Field>
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

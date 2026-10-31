import { useEffect, useState } from "react";
import { api, errorMessage, fileUrl } from "../api";
import { ErrorBox, Field } from "../components/ui";

const LEAD_SIZES = [["01", "ME"], ["03", "EPP"], ["05", "Grande"], ["00", "Não informado"]];
const AREA_CODES = {
  PR: ["41", "42", "43", "44", "45", "46"], RS: ["51", "53", "54", "55"], SC: ["47", "48", "49"],
  SP: ["11", "12", "13", "14", "15", "16", "17", "18", "19"], RJ: ["21", "22", "24"], ES: ["27", "28"],
  MG: ["31", "32", "33", "34", "35", "37", "38"], MS: ["67"], MT: ["65", "66"], GO: ["62", "64"], DF: ["61"],
  BA: ["71", "73", "74", "75", "77"], SE: ["79"], AL: ["82"], PE: ["81", "87"], PB: ["83"], RN: ["84"],
  CE: ["85", "88"], PI: ["86", "89"], MA: ["98", "99"], PA: ["91", "93", "94"], AP: ["96"], AM: ["92", "97"],
  RR: ["95"], AC: ["68"], RO: ["69"], TO: ["63"],
};
const stateList = (states) => (states || "").toUpperCase().split(",").map((uf) => uf.trim()).filter((uf) => AREA_CODES[uf]);

export default function Settings() {
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);
  const [catalogBusy, setCatalogBusy] = useState(false);

  useEffect(() => {
    api.get("/settings").then((r) => setForm(r.data)).catch((e) => setError(errorMessage(e)));
  }, []);

  // The catalog is saved on its own (not by "Salvar"), so unsaved edits in the form are kept
  async function catalogRequest(request) {
    setError(""); setOk(""); setCatalogBusy(true);
    try {
      const { data } = await request();
      setForm((f) => ({ ...f, catalog_url: data.catalog_url }));
      setOk(data.catalog_url ? "Catálogo enviado." : "Catálogo removido.");
    } catch (err) { setError(errorMessage(err)); } finally { setCatalogBusy(false); }
  }
  function uploadCatalog(file) {
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    catalogRequest(() => api.post("/settings/catalog", body));
  }
  const removeCatalog = () => catalogRequest(() => api.delete("/settings/catalog"));

  // A toggle over one of the comma-separated settings (DDDs, company sizes)
  function chip(code, label, key) {
    const current = (form[key] || "").split(",").filter(Boolean);
    const on = current.includes(code);
    const next = on ? current.filter((c) => c !== code) : [...current, code];
    return (
      <button type="button" key={code} className={`period-chip ${on ? "on" : ""}`} aria-pressed={on}
        onClick={() => setForm({ ...form, [key]: next.join(",") })}>{label}</button>
    );
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
        // a DDD of a state taken off the list would leave the other states empty
        lead_area_codes: (form.lead_area_codes || "").split(",")
          .filter((c) => stateList(form.lead_states).some((uf) => AREA_CODES[uf].includes(c))).join(","),
        lead_weekly_release: Number(form.lead_weekly_release) || 0,
        leads_for_sellers: !!form.leads_for_sellers,
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
            <h3>Catálogo</h3>
            <div className="form-grid">
              <div className="span-2">
                {form.catalog_url
                  ? <p><a href={fileUrl(form.catalog_url)} target="_blank" rel="noopener noreferrer">Abrir catálogo atual</a></p>
                  : <p className="muted">Nenhum catálogo enviado.</p>}
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <label className="btn">
                    {catalogBusy ? "Enviando…" : form.catalog_url ? "Trocar PDF" : "Enviar PDF"}
                    <input type="file" accept=".pdf,application/pdf" hidden disabled={catalogBusy}
                      onChange={(e) => { uploadCatalog(e.target.files[0]); e.target.value = ""; }} />
                  </label>
                  {form.catalog_url && <button type="button" className="btn" disabled={catalogBusy} onClick={removeCatalog}>Remover</button>}
                </div>
                <small className="muted">
                  PDF de até 40 MB. Os vendedores mandam o link para as lojas pelo botão "Enviar catálogo" em Prospecção.
                </small>
              </div>
            </div>
          </section>

          <section className="panel">
            <h3>Prospecção</h3>
            <label className="switch-row">
              <span>
                Liberar a Prospecção para os vendedores
                <small className="muted">Desligado, só administradores veem a tela.</small>
              </span>
              <input type="checkbox" role="switch" className="switch" checked={!!form.leads_for_sellers}
                onChange={(e) => setForm({ ...form, leads_for_sellers: e.target.checked })} />
            </label>

            <div className="settings-group">
              <div className="settings-group-head">
                <h4>Onde buscar</h4>
                <small className="muted">Mudar um filtro faz a próxima importação buscar as lojas de novo.</small>
              </div>
              <div className="form-grid">
                <Field label="Estados">
                  <input placeholder="PR, RS, SC" value={form.lead_states || ""}
                    onChange={(e) => setForm({ ...form, lead_states: e.target.value })} />
                  <small className="muted">Siglas separadas por vírgula.</small>
                </Field>
                <Field label="CNAEs">
                  <input placeholder="4781-4/00" value={form.lead_cnaes || ""}
                    onChange={(e) => setForm({ ...form, lead_cnaes: e.target.value })} />
                  <small className="muted">Separe por vírgula. Padrão: 4781-4/00 (vestuário e acessórios).</small>
                </Field>
                <div className="field span-2">
                  <span>DDDs</span>
                  {stateList(form.lead_states).map((uf) => (
                    <div key={uf} className="ddd-row">
                      <strong>{uf}</strong>
                      <div className="chip-row">
                        {AREA_CODES[uf].map((code) => chip(code, code, "lead_area_codes"))}
                      </div>
                    </div>
                  ))}
                  <small className="muted">Nenhum marcado = todos os DDDs dos estados acima.</small>
                </div>
              </div>
            </div>

            <div className="settings-group">
              <div className="settings-group-head"><h4>Quais lojas entram</h4></div>
              <div className="form-grid">
                <div className="field">
                  <span>Porte da empresa</span>
                  <div className="chip-row">{LEAD_SIZES.map(([code, label]) => chip(code, label, "lead_sizes"))}</div>
                </div>
                <Field label="Abertas há pelo menos (meses)">
                  <input type="number" min="0" max="120" step="1" value={form.lead_min_age_months ?? ""}
                    onChange={(e) => setForm({ ...form, lead_min_age_months: e.target.value })} />
                </Field>
                <div className="span-2 settings-checks">
                  <label className="check"><input type="checkbox" checked={form.lead_exclude_mei}
                    onChange={(e) => setForm({ ...form, lead_exclude_mei: e.target.checked })} /> Excluir MEI</label>
                  <label className="check"><input type="checkbox" checked={form.lead_head_office_only}
                    onChange={(e) => setForm({ ...form, lead_head_office_only: e.target.checked })} /> Só a matriz (sem filiais)</label>
                  <label className="check"><input type="checkbox" checked={form.lead_require_contact}
                    onChange={(e) => setForm({ ...form, lead_require_contact: e.target.checked })} /> Só com telefone na Receita</label>
                </div>
              </div>
            </div>

            <div className="settings-group">
              <div className="settings-group-head"><h4>Distribuição</h4></div>
              <div className="form-grid">
                <Field label="Lojas sugeridas por vendedor, por semana">
                  <input type="number" min="0" max="500" step="1" value={form.lead_weekly_release ?? ""}
                    onChange={(e) => setForm({ ...form, lead_weekly_release: e.target.value })} />
                  <small className="muted">Só uma sugestão: nada é liberado sem o administrador.</small>
                </Field>
              </div>
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

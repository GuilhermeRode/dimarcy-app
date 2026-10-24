import { useState } from "react";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { Avatar, ErrorBox, Field, PasswordInput } from "../components/ui";

export default function Profile() {
  const { user, updateUser } = useAuth();
  const [form, setForm] = useState({
    name: user.name, email: user.email, current_password: "", new_password: "",
  });
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);

  const f = (k) => ({ value: form[k], onChange: (e) => setForm({ ...form, [k]: e.target.value }) });

  async function save(e) {
    e.preventDefault();
    setError(""); setOk(""); setBusy(true);
    try {
      const { data } = await api.put("/auth/me", form);
      updateUser(data);
      setForm({ ...form, current_password: "", new_password: "" });
      setOk("Perfil atualizado com sucesso.");
    } catch (err) {
      setError(errorMessage(err));
    } finally { setBusy(false); }
  }

  // Saved on toggle, apart from the access form (which may hold a half-typed password).
  async function setQuickQuantity(on) {
    setError(""); setOk("");
    try {
      const { data } = await api.put("/auth/me", { name: user.name, email: user.email, quick_quantity: on });
      updateUser(data);
    } catch (err) { setError(errorMessage(err)); }
  }

  async function onAvatarPick(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(""); setOk("");
    const body = new FormData();
    body.append("file", file);
    try {
      const { data } = await api.post("/auth/me/avatar", body, { headers: { "Content-Type": "multipart/form-data" } });
      updateUser(data);
    } catch (err) { setError(errorMessage(err)); }
  }

  async function removeAvatar() {
    setError(""); setOk("");
    try {
      const { data } = await api.delete("/auth/me/avatar");
      updateUser(data);
    } catch (err) { setError(errorMessage(err)); }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>Meu perfil</h1>
        <p className="muted">Edite seus dados de acesso e foto.</p>
      </header>

      <section className="panel profile-header">
        <Avatar url={user.avatar_url} name={user.name} size="lg" />
        <div className="profile-avatar-actions">
          <label className="btn btn-light">
            Trocar foto
            <input type="file" accept="image/*" hidden onChange={onAvatarPick} />
          </label>
          {user.avatar_url && <button type="button" className="btn-x" style={{ fontSize: "0.85rem" }} onClick={removeAvatar}>Remover foto</button>}
        </div>
      </section>

      <section className="panel">
        <h3>Dados de acesso</h3>
        <form onSubmit={save} className="form-grid">
          <Field label="Nome" span={2}><input required {...f("name")} /></Field>
          <Field label="E-mail" span={2}><input type="email" required {...f("email")} /></Field>
          <Field label="Senha atual" span={2}>
            <PasswordInput autoComplete="current-password" placeholder="Necessária para trocar e-mail ou senha" {...f("current_password")} />
          </Field>
          <Field label="Nova senha (deixe em branco para manter)" span={2}>
            <PasswordInput autoComplete="new-password" minLength={10} {...f("new_password")} />
          </Field>
          <div className="span-2"><ErrorBox msg={error} /></div>
          {ok && <div className="span-2 muted">{ok}</div>}
          <div className="actions span-2">
            <button className="btn btn-primary" disabled={busy}>Salvar alterações</button>
          </div>
        </form>
      </section>

      <section className="panel">
        <h3>Preferências</h3>
        <label className="switch-row">
          <span>
            Usar botões +1 / +2 na grade do pedido
            <small className="muted">Tocar na grade de quantidades soma sem abrir o teclado.</small>
          </span>
          {/* on by default; an older cached user has no field */}
          <input type="checkbox" role="switch" className="switch switch-sm" checked={user.quick_quantity !== false}
            onChange={(e) => setQuickQuantity(e.target.checked)} />
        </label>
      </section>
    </div>
  );
}

import { useRef, useState } from "react";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { Avatar, ErrorBox, Field } from "../components/ui";

export default function Profile() {
  const { user, updateUser } = useAuth();
  const fileInput = useRef(null);
  const [form, setForm] = useState({
    name: user.name, email: user.email, current_password: "", new_password: "",
  });
  const [theme, setTheme] = useState(user.theme || "light");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);

  const f = (k) => ({ value: form[k], onChange: (e) => setForm({ ...form, [k]: e.target.value }) });

  function chooseTheme(t) {
    setTheme(t);
    document.documentElement.dataset.theme = t; // live preview
  }

  async function save(e) {
    e.preventDefault();
    setError(""); setOk(""); setBusy(true);
    try {
      const { data } = await api.put("/auth/me", { ...form, theme });
      updateUser(data);
      setForm({ ...form, current_password: "", new_password: "" });
      setOk("Perfil atualizado com sucesso.");
    } catch (err) {
      document.documentElement.dataset.theme = user.theme || "light"; // revert failed preview
      setError(errorMessage(err));
    } finally { setBusy(false); }
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
        <p className="muted">Edite seus dados de acesso, foto e aparência do app.</p>
      </header>

      <section className="panel profile-header">
        <Avatar url={user.avatar_url} name={user.name} size="lg" />
        <div className="profile-avatar-actions">
          <button type="button" className="btn btn-light" onClick={() => fileInput.current.click()}>Trocar foto</button>
          {user.avatar_url && <button type="button" className="btn-x" style={{ fontSize: "0.85rem" }} onClick={removeAvatar}>Remover foto</button>}
          <input ref={fileInput} type="file" accept="image/*" hidden onChange={onAvatarPick} />
        </div>
      </section>

      <section className="panel">
        <h3>Aparência</h3>
        <div className="theme-options">
          <button type="button" className={`theme-option ${theme === "light" ? "on" : ""}`} onClick={() => chooseTheme("light")}>
            <span className="theme-swatch theme-swatch-light" />
            Claro
          </button>
          <button type="button" className={`theme-option ${theme === "dark" ? "on" : ""}`} onClick={() => chooseTheme("dark")}>
            <span className="theme-swatch theme-swatch-dark" />
            Escuro
          </button>
        </div>
      </section>

      <section className="panel">
        <h3>Dados de acesso</h3>
        <form onSubmit={save} className="form-grid">
          <Field label="Nome" span={2}><input required {...f("name")} /></Field>
          <Field label="E-mail" span={2}><input type="email" required {...f("email")} /></Field>
          <Field label="Senha atual" span={2}>
            <input type="password" placeholder="Necessária para trocar e-mail ou senha" {...f("current_password")} />
          </Field>
          <Field label="Nova senha (deixe em branco para manter)" span={2}>
            <input type="password" minLength={6} {...f("new_password")} />
          </Field>
          <div className="span-2"><ErrorBox msg={error} /></div>
          {ok && <div className="span-2 muted">{ok}</div>}
          <div className="actions span-2">
            <button className="btn btn-primary" disabled={busy}>Salvar alterações</button>
          </div>
        </form>
      </section>
    </div>
  );
}

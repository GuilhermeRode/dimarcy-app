import logoFull from "../assets/logo-full.png";

// Built and published by .github/workflows/desktop.yml; "latest" always serves the newest installer.
const INSTALLER_URL = "https://github.com/GuilhermeRode/dimarcy-app/releases/latest/download/Di-Marcy-Pedidos-Setup.exe";

// Unlisted page at /download (no menu links to it): the desktop installer for Windows.
export default function Download() {
  return (
    <main className="download-page">
      <section className="download-card">
        <img src={logoFull} alt="Di Marcy" className="download-logo" />
        <h1>Di Marcy Pedidos para Windows</h1>
        <p className="muted">O mesmo sistema do navegador, num app no seu computador, com atalho na área de trabalho.</p>
        <a className="btn btn-primary download-btn" href={INSTALLER_URL}>Baixar para Windows</a>
        <ol className="download-steps">
          <li>Abra o arquivo baixado (<strong>Di-Marcy-Pedidos-Setup.exe</strong>).</li>
          <li>Se o Windows mostrar “O Windows protegeu o computador”, clique em <strong>Mais informações</strong> e depois em <strong>Executar assim mesmo</strong>.</li>
          <li>Entre com o mesmo e-mail e senha que você já usa.</li>
        </ol>
        <a className="download-web" href="/">Prefiro usar no navegador</a>
      </section>
    </main>
  );
}

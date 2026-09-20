# Hospedagem pública gratuita do Di Marcy Pedidos (Electron + Mobile)

**Data:** 2026-09-20
**Status:** design aprovado, aguardando plano de implementação

## Contexto e motivação

Hoje o backend (FastAPI + SQLite) roda na máquina local do usuário, acessível
apenas pela rede Wi-Fi de casa (`192.168.18.165`). O app desktop (Electron) e o
app mobile (Capacitor/Android) só funcionam quando o dispositivo está na mesma
rede local.

O objetivo é que vendedores usem o app de **qualquer lugar**, em uso real de
produção (não só testes), sem custo de hospedagem.

## Restrições

- **Gratuito**: sem custo mensal de hospedagem.
- **Sempre disponível**: sem "sleep"/cold-start — descarta hospedagens PaaS
  gratuitas comuns (Render, Railway free, etc.), que dormem após inatividade.
- **Uso real de produção**: vendedores dependem do sistema no dia a dia.
- Domínio próprio já existe (`dimarcy.com.br`, gerenciado via painel Turbo
  Cloud por terceiros), mas é usado pelo site institucional — não pode ser
  afetado.

## Abordagens consideradas

1. **Auto-hospedar no PC do usuário + túnel gratuito (Cloudflare Tunnel)** —
   descartada: disponibilidade depende do PC de casa e da internet residencial
   nunca caírem (queda de luz, reinício do Windows, queda de internet = app
   fora do ar). Frágil demais para uso real.
2. **VM "always free" em nuvem (Oracle Cloud / Google Cloud free tier)** —
   **escolhida**. Servidor de verdade, 24h, independente do PC de casa.
3. Hospedagem paga barata (~R$25-30/mês) — descartada por violar a restrição
   de custo zero; mantida como alternativa futura caso o usuário reconsidere.

## Decisão de arquitetura

### Infraestrutura

- VM gratuita "para sempre" na **Oracle Cloud** (Always Free tier), Ubuntu.
  (Google Cloud e2-micro como alternativa caso a Oracle tenha problema de
  disponibilidade de vaga na região do usuário.)
- Backend FastAPI roda como **serviço systemd** — reinicia sozinho se cair ou
  se a VM reiniciar.
- **Caddy** como reverse proxy na frente do backend, gerando e renovando
  HTTPS automaticamente via Let's Encrypt.
- **SQLite é mantido** — o disco da VM é persistente (ao contrário de
  hospedagens serverless), então não há necessidade de migrar para Postgres.
  Decisão deliberada de não adicionar complexidade sem necessidade real, dado
  o volume de uso de uma pequena empresa.

### DNS / domínio

- Subdomínio **`pedidos.dimarcy.com.br`** apontando (registro A) para o IP
  público da VM, criado no painel Turbo Cloud onde o domínio já é gerenciado.
- Não afeta o site institucional existente no domínio raiz.

### Clientes

**Electron (desktop):**
- Já carrega os arquivos empacotados em produção (`win.loadFile(...)`),
  independente de servidor local — nenhuma mudança de código necessária.
- `frontend/.env` → `VITE_API_URL=https://pedidos.dimarcy.com.br/api`, depois
  regenerar o instalador (`vite build && electron-builder --win`) e redistribuir.

**Mobile (Capacitor/Android):**
- Hoje está em **modo live-reload** (`capacitor.config.ts` com bloco
  `server.url` apontando para o Vite dev server na rede local) — só funciona
  em casa, tanto a tela quanto a API.
- Para uso real: remover o bloco `server.url`, rodar `npm run build` +
  `npx cap sync android`, e gerar um APK que carrega as telas embutidas no
  próprio app, consumindo a API só pela internet.
- **Trade-off aceito pelo usuário**: isso muda o fluxo de desenvolvimento —
  hoje uma edição de código atualiza o celular na hora (live-reload); em
  modo produção, cada mudança exige gerar um novo APK e reinstalar. Vamos
  manter as duas configurações disponíveis (uma para desenvolvimento local
  com live-reload, outra para gerar a versão real distribuída aos
  vendedores).

### Segurança

- HTTPS obrigatório (via Caddy/Let's Encrypt) — protege login e senha
  trafegando pela internet.
- Acesso SSH à VM só por chave (sem senha).
- Firewall liberando apenas as portas 22 (SSH), 80 e 443.
- Segredos (`SECRET_KEY`, credenciais SMTP) digitados diretamente no `.env`
  do servidor, nunca commitados no Git — mesmo padrão já usado localmente.
- `CORS_ORIGINS=*` é mantido como está — a autenticação é via token JWT no
  header `Authorization`, não via cookie, então o risco de CORS aberto é
  baixo para esse caso de uso (Electron/Capacitor, não uma página web pública
  de terceiros).

## Plano de validação

Após o deploy, testar (com o celular **fora da rede Wi-Fi de casa**, ex. só
no 4G):
1. Login pelo app mobile e pelo Electron reconstruído.
2. Criar um pedido de teste e marcar como "Entregue".
3. Confirmar que a notificação por e-mail (`di_marcy@hotmail.com`) chega
   normalmente vindo do servidor na nuvem.
4. Confirmar que os dados persistem depois de reiniciar a VM manualmente
   (valida que o SQLite está num disco persistente, não temporário).

## Fora de escopo (deliberadamente não incluído agora)

- Migração de banco de dados para Postgres.
- Atualização automática do instalador Electron (auto-update).
- CI/CD automatizado para deploys futuros — deploy inicial será manual/guiado.
- Distribuição do APK via Google Play Store (fica só como instalação manual/
  side-load, como já é feito hoje).
- Configuração de backup automático do banco na VM (pode ser um próximo
  passo depois que o essencial estiver no ar).

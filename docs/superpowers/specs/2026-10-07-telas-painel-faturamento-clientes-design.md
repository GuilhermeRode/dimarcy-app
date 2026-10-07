# Redesenho das telas Painel, Faturamento e Clientes

**Data:** 2026-10-07 (revisado após revisão de correção e de segurança)
**Referência visual:** `docs/Refatoração de três telas admin/Di Marcy Admin.dc.html` (protótipo com dados fictícios; não versionado porque os prints contêm dados de clientes)

## Objetivo

Trazer as três telas para o visual do protótipo, usando só dados reais do app, e tornar
cada tela mais útil para a decisão comercial:

- **Painel:** mostrar de relance quanto se vendeu, contra o período anterior e contra a meta,
  e apontar o que precisa de ação (clientes em risco, pedidos atrasados, cadastros sem compra).
- **Faturamento:** comparar vendedores entre si e contra as próprias metas.
- **Clientes:** encontrar oportunidades na carteira (quem parou de comprar, quem nunca comprou)
  e agir direto dali (novo pedido, WhatsApp).

## Fora do escopo

- Menu lateral redesenhado (logo em texto, contadores) — o menu atual fica.
- Etapas de pedido que o app não tem ("Aguardando aprovação", "Pronto p/ envio") — usamos as 6 reais.
- Mapa de calor por dia, contas a receber e maiores pedidos — o app não registra pagamentos.
- Tela do mapa de clientes por cidade (`/customers-by-city`) — continua como está.
- Redesenho do app Electron. **Exceção:** o reforço de links externos em `electron/main.cjs`
  (seção Segurança), porque o botão de WhatsApp roda também no app de desktop.

## Decisões

| Tema | Decisão |
|---|---|
| Onde calcular | No servidor: status do cliente, atraso, meta do período, variação vs. período anterior. As telas só desenham. |
| "Hoje" | Servidor usa o horário de Brasília (UTC−3 fixo; o Brasil não tem horário de verão desde 2019). Frontend monta datas com o relógio local (`getFullYear/getMonth/getDate`), nunca `toISOString()`. |
| Metas | Meta **mensal** da empresa (Configurações) e meta **mensal** por usuário (Usuários). `NULL` ou `0` = sem meta. |
| Meta do período | **Proporcional aos dias do período**, para todos os botões: `meta mensal × dias do período ÷ 30,4`. Ex.: "Este mês" no dia 7 compara com 7 dias de meta — o anel mostra se a equipe está no ritmo. Rótulo: "Meta do período · R$ X". |
| Sem meta | Anel e aba "% da meta" não aparecem (nunca "0%"). |
| Período | Botões 7 dias / Este mês / Este ano + "Personalizado" (mostra os campos de data). Máximo de 2 anos por consulta. |
| Gráficos | Recharts (já instalado) para a linha de 12 meses e a rosca; CSS puro para barras. Nenhuma biblioteca nova. |
| O que conta como venda | `SALE_STATUSES` (confirmado, em produção, enviado, entregue) — mesma regra do faturamento atual. |
| Status do cliente | Pela data da última **venda**: `never_ordered` "Nunca comprou" (nenhuma venda — orçamentos e cancelados não contam) · `active` "Ativo" (≤ 60 dias) · `at_risk` "Em risco" (61–150) · `inactive` "Inativo" (> 150). |
| Pedido atrasado | `delivery_date` < hoje e status `confirmed` ou `in_production`. |
| Pedidos visíveis para vendedor | Em **todas** as somas (Painel, Faturamento, Clientes): só pedidos com `seller_id` = ele — a mesma regra de `/orders`. Clientes visíveis: `owner_id` = ele. |
| Clientes por página | 20. |
| Saudação | 00:00–04:59 "Boa noite", 05–11:59 "Bom dia", 12–17:59 "Boa tarde", 18+ "Boa noite" (já implementado). |

## Regras num lugar só

Em `backend/app/models.py`, ao lado de `SALE_STATUSES`:

- `ACTIVE_DAYS = 60`, `AT_RISK_DAYS = 150`, `LATE_STATUSES = ["confirmed", "in_production"]`.
- `customer_status(last_sale: date | None, today: date) -> str`.

Em `backend/app/` um helper `today_br() -> date` (UTC−3). Todo cálculo de "hoje" no backend usa ele
(`dashboard.py` hoje usa `date.today()` — passa a usar `today_br()`).

No frontend, `format.js` ganha só rótulos e cores: `CUSTOMER_STATUS = { active: {label, color}, … }`,
no mesmo padrão do mapa de status de pedido existente, e `localDate(d)` / `addDays` / `startOfMonth`
com datas locais (substituindo as cópias em `Dashboard.jsx`, `Revenue.jsx` e o `toISOString()` de `OrderForm.jsx`).

## Dados e API

### Banco

- `app_settings.monthly_goal NUMERIC(12,2) DEFAULT 0`.
- `users.monthly_goal NUMERIC(12,2)` (nulo).
- Migração: generalizar `_ensure_user_columns` de `main.py` para `_ensure_columns(table, {coluna: ddl})`
  e usá-la para `users` e `app_settings`. Nenhum dado é apagado. O servidor roda com um único processo
  (sem `--workers`), então não há corrida entre ALTERs.
- `Numeric` volta como `Decimal`: converter com `float()` antes de qualquer conta.

### Schemas e escrita

- `monthly_goal: float | None = Field(None, ge=0, le=9_999_999_999)` em `AppSettingsIn` e `UserIn`
  (rejeita negativo, infinito e valor que estoura a coluna).
- **A meta da empresa não vai no `AppSettingsOut` público** (`GET /api/settings` é usado por vendedores
  no formulário de pedido). `GET /api/settings` inclui `monthly_goal` só quando quem pede é admin
  (schema `AppSettingsAdminOut`); `PUT /api/settings` (já admin-only) recebe e devolve o completo.
- `Settings.jsx` passa a enviar `monthly_goal` no PUT (hoje monta o corpo à mão — sem isso, salvar apagaria a meta).
- `users.py`: `POST` e `PUT` atribuem `monthly_goal` (hoje copiam campo a campo).
  `Users.jsx` envia campo vazio como `null`, não `""`.
- `UserOut` ganha `monthly_goal`. Vendedor só o recebe sobre si mesmo (`/auth/me`, login);
  `/users` já é admin-only.

### `GET /api/dashboard?start&end` (existente)

Validação: `start > end` ou período > 731 dias → 400 "Período inválido." Padrões continuam
(1º de janeiro até hoje).

Campos novos:

- `previous_kpis`: os mesmos `kpis` para o período anterior de mesma duração (termina no dia anterior a `start`).
  Substitui a segunda chamada que o Painel faz hoje (`previousPeriod` sai do frontend).
- `sales_series`: `[{ "label": "07/10", "start": "2026-10-07", "value": 1234.5 }]`, só vendas (`SALE_STATUSES`).
  Até 31 dias → um ponto por dia; mais → um por semana (segunda a domingo). A primeira e a última semana
  são cortadas nos limites do período; `start` é o primeiro dia do ponto dentro do período e `label` é `dd/mm` desse dia.
- `goal`: meta da empresa no período (proporcional), ou `null` sem meta. **Só para admin**; vendedor recebe a própria.
- `by_seller`: cada item ganha `id`, `avatar_url` e `goal` (meta do usuário no período ou `null`).
  Para admin, inclui com zeros todo usuário ativo com `role = "seller"` sem vendas no período, mais qualquer
  usuário que vendeu no período (admin que vende aparece só se vendeu). Vendedor recebe só a si mesmo.
- `alerts`: `{ "customers_at_risk": n, "customers_never_ordered": n, "late_orders": n, "oldest_late_days": n | null }`.
  Carteira inteira (não depende do período). Contagens de clientes usam `customer_status` com a mesma consulta
  agregada de `/customers/overview` — o número do alerta e o da lista filtrada têm de bater.

### `GET /api/customers/overview` (nova)

Declarada antes de `GET /customers/{cid}`. Lista completa (~525 clientes; sem paginação no servidor).

```json
{
  "id": 1, "name": "…", "city": "Rio do Sul", "state": "SC", "phone": "…", "document": "…",
  "owner_id": 3, "owner_name": "Marcia", "created_at": "2024-03-01T…",
  "total": 18240.0, "orders": 6, "last_order_date": "2026-09-12",
  "status": "active",
  "colors": ["Preto", "Vinho"],
  "recent_orders": [{ "id": 4812, "date": "2026-09-12", "pieces": 40, "total": 1840.0 }]
}
```

- Clientes: admin recebe todos (inclusive `owner_id` nulo); vendedor, só `owner_id` = ele.
- Pedidos agregados: só `SALE_STATUSES`; para vendedor, só `seller_id` = ele (assim todo `recent_orders.id`
  abre em `/orders/<id>` para quem vê).
- `colors`: até 3, por peças. `recent_orders`: até 3, mais recentes.
- Desempenho: **uma** consulta de clientes (com `joinedload(Customer.owner)`) e **uma** de pedidos de venda
  já filtrados (itens vêm por `selectin`), agregadas em Python. Nada de `customer.orders` por cliente.

### `GET /api/orders?late=1` (existente, filtro novo)

`late=true` filtra `delivery_date < hoje` e status em `LATE_STATUSES`. É o destino do alerta de pedidos atrasados
(admin e vendedor), e `Orders.jsx` mostra a etiqueta "Atrasados ×" para remover o filtro.

## Segurança

- Vendedor nunca recebe: meta da empresa, meta ou números de outro usuário, clientes de outro dono,
  pedidos de outro vendedor. Coberto por teste.
- WhatsApp: `digits = phone.replace(/\D/g, "")`; remove `55` inicial se sobrar 12–13 dígitos; botão ativo só com
  10–11 dígitos; link `https://wa.me/55<digits>` num `<a target="_blank" rel="noopener noreferrer">`.
  O telefone nunca entra na URL sem passar por esse filtro.
- `electron/main.cjs`: `setWindowOpenHandler` só repassa a `shell.openExternal` URLs `https:`; e um
  `will-navigate` impede a janela do app de navegar para fora do próprio app.
- Capacitor (Android): link externo abre fora do app pelo sistema; conferir no aparelho.
- Parâmetros de URL: valores fora da lista são ignorados (`status`, `sort`, `seller`); `page` limitado ao intervalo
  válido; `q` só filtra texto em memória; `?customer=` vira `Number()` e só é aceito se o cliente estiver na lista
  que o usuário já recebe (o servidor também valida dono em `POST /orders`). Nenhum valor de URL vai para `href` ou HTML cru.
- Respostas limitadas: período ≤ 2 anos; overview traz no máximo 3 pedidos e 3 cores por cliente.

## Telas

Visual do protótipo (cards escuros `#0c2140`, cantos arredondados), com classes em `frontend/src/styles.css`,
reaproveitando as existentes e respeitando o tema escuro. Textos em pt-BR, código em inglês.

### Componentes (em `frontend/src/components/`)

- `PeriodPicker` — botões + "Personalizado" com datas locais; devolve `{start, end, preset}`. Painel e Faturamento.
- `usePeriodData(start, end)` — busca `/dashboard` e devolve `{data, error, loading}`. Painel e Faturamento.
- `TeamRanking` — bloco escuro "Fulano lidera em …" com abas Faturamento / Pedidos / Peças / % da meta
  (aba de meta só se algum `goal`); um card por vendedor; prop `showGoalGap` liga "meta do período e quanto falta" (Faturamento).
- `RevenueHero` — card escuro de faturamento (valor, variação, `sales_series`, anel de meta).
- `AlertStrip` — os três alertas.
- `Delta` (variação %, já existe em `Dashboard.jsx`) sai para `components/` e é usado por todos.
  Variação não aparece quando o período anterior é 0.

`Dashboard.jsx` e `Revenue.jsx` ficam só organizando seções.

### Painel (`/`, todos)

1. Cabeçalho: data por extenso, saudação + primeiro nome, `PeriodPicker`.
2. `RevenueHero` (admin: clique leva a `/revenue`) + coluna branca: Pedidos fechados, Peças vendidas, Ticket médio, com `Delta`.
3. `AlertStrip` (só alertas com contagem > 0; some se todos forem 0):
   clientes em risco → `/customers?status=at_risk`; pedidos atrasados → `/orders?late=1`;
   cadastros sem compra → `/customers?status=never_ordered`.
4. Linha de 12 meses (Recharts, tooltip) + rosca das 6 situações; passar o mouse destaca a fatia e mostra número e % no centro.
5. `TeamRanking` — só admin.
6. Cores mais vendidas, Peças por tamanho, Produtos mais vendidos.
7. Melhores clientes (top 5, "Ver todos" → `/customers?sort=total`) e Clientes por cidade (admin, "Ver mapa"; oculto no build Android, como hoje).
8. Card sem dados: "Sem vendas no período."

### Faturamento (`/revenue`, só admin)

1. Cabeçalho "Faturamento" + `PeriodPicker`.
2. Card escuro: faturamento total + `Delta`; Pedidos, Peças, Ticket médio; barra de participação por vendedor com legenda "Nome 36%".
3. `TeamRanking` com `showGoalGap`.
4. Por cidade: 5 cidades com mais faturamento + "Outras", valor e barra.

### Clientes (`/customers`, todos)

1. Cabeçalho "Clientes" + subtítulo + "+ Cadastrar cliente" (formulário atual).
2. Filtros na URL — valores aceitos:
   `q` (texto) · `status` = `active|at_risk|inactive|never_ordered` · `state` · `city` ·
   `seller` = id do vendedor ou `none` (sem vendedor; só admin) · `color` (nome) ·
   `sort` = `total|orders|recent|name` (padrão `total`) · `page`.
   Busca por nome, cidade ou CPF/CNPJ, ignorando acento e maiúscula. Cidade lista só as do estado escolhido.
   Etiquetas removíveis + "Limpar tudo".
3. Dados de `/customers/overview` — **a tela deixa de baixar `/orders`** (hoje `Customers.jsx` baixa todos os pedidos).
4. Tabela: Cliente (iniciais, nome, cidade/UF), Vendedor (só admin), Total, Pedidos, Status colorido.
   20 por página, "Mostrando 1–20 de N". Vazio: "Nenhum cliente com esses filtros."
5. Painel lateral: iniciais, nome, cidade · telefone, status; **Novo pedido** (`/orders/new?customer=<id>`),
   **WhatsApp** (regra da seção Segurança; desabilitado sem telefone válido), **Editar** (formulário atual, com Excluir);
   total comprado, pedidos, ticket médio, cliente desde; vendedor e cores; 3 últimos pedidos clicáveis
   ou "Ainda sem compras. Bom momento para um primeiro contato."
6. Celular: lista de cartões; painel em tela cheia com botão de fechar.
7. Depois de salvar/excluir no formulário, recarrega o overview.

### Formulário de pedido

- `OrderForm`, só em `/orders/new` (sem `id`), aplica `?customer=<id>` pela regra de Segurança.
- Com cliente pré-escolhido, o aviso de "alterações não salvas" só dispara se houver itens ou se o cliente
  for trocado (hoje dispara assim que há cliente — `OrderForm.jsx:209`).
- Data padrão do pedido passa a usar a data local (hoje `toISOString()` dá o dia seguinte após 21h).

### Configurações e Usuários

- Configurações: campo "Meta mensal da empresa (R$)" (vazio = sem meta).
- Usuários: campo "Meta mensal (R$)" no formulário (vazio = sem meta).

## Testes

`backend/test_dashboard.py`, no estilo de `test_security.py` (SQLite temporário, `TestClient`):

- `customer_status`: 60/61 e 150/151 dias; sem venda; só orçamento/cancelado = `never_ordered`.
- Atraso: confirmado/em produção vencido conta; enviado/entregue/cancelado/vence hoje não.
- `sales_series`: 7 dias = 7 pontos diários; 1º jan–hoje = semanal com cortes nas pontas.
- `previous_kpis`: período anterior de mesma duração.
- Período inválido (`start > end`, > 731 dias) → 400.
- Meta: proporcional aos dias; `null` sem meta; `PUT /settings` com negativo → 422.
- Permissões: vendedor não recebe meta da empresa (nem em `/dashboard` nem em `GET /settings`), metas/números de
  outro vendedor, clientes de outro dono, nem pedidos de outro vendedor em cliente seu reatribuído.
- Alerta "em risco" = quantidade de `at_risk` no overview.
- `/orders?late=1` filtra corretamente.

`backend/test_security.py` continua passando. Frontend: `npm run build` sem erro e conferência manual das três telas
com admin e vendedor, desktop e largura de celular; WhatsApp no desktop (Electron) e no Android.

## Ordem de implementação

1. Regras e helpers (`today_br`, `customer_status`, constantes) + migração + schemas de meta, com testes.
2. `/dashboard` (novos campos, validação) e `/customers/overview`, `/orders?late=1`, com testes.
3. Campos de meta em Configurações e Usuários.
4. Helpers de data em `format.js`; componentes compartilhados.
5. Clientes (+ `?customer=` no `OrderForm`, Electron links).
6. Painel.
7. Faturamento.

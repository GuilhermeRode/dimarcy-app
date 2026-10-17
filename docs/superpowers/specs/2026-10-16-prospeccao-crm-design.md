# Prospecção de clientes novos + mini-CRM

**Data:** 2026-10-16 (revisado após revisão contra o código e verificação dos arquivos reais da Receita)

## Objetivo

Ajudar os vendedores a gerar vendas novas:

- **Prospecção:** mostrar ao vendedor lojas de vestuário que ainda não são clientes, dentro da
  região que ele atende, a partir dos dados abertos de CNPJ da Receita Federal.
- **Mini-CRM:** registrar cada contato (com lead ou cliente) e lembrar o vendedor do retorno
  combinado ("Retornos de hoje").

## Fora do escopo

- IA (ranking ou mensagem gerada). Ranking por regras fixas e mensagem de WhatsApp com texto fixo.
- Google Places / APIs pagas de CNPJ. Pode virar etapa futura para enriquecer contatos.
- Botão "importar agora" na tela — a importação roda pelo timer (ver "Importação").
- Editar ou apagar contato registrado (histórico só de inclusão). Exportar leads.
- Mudar o dono de clientes existentes por causa da região: a região vale **só para leads**.
- CNAE secundário: filtra só pelo CNAE **principal**.
- Lista oficial de municípios para o autocompletar da região (usa cidades de clientes e leads; texto livre
  continua aceito).

## Decisões

| Tema | Decisão |
|---|---|
| Fonte dos dados | Dados abertos de CNPJ da Receita Federal (gratuito, mensal), via WebDAV público do Nextcloud da Receita. |
| CNAEs | Lista editável pelo admin em Configurações; padrão só `4781400` (comércio varejista de artigos do vestuário e acessórios). |
| Região do vendedor | Lista explícita de cidades (cidade + UF) por vendedor, definida pelo admin. **Uma cidade pertence a no máximo um vendedor** (constraint única no banco). |
| Alcance da região | Só leads. Clientes atuais continuam com o dono atual, mesmo em cidade de outro vendedor. |
| Dono do lead | **Não é gravado**: calculado pela cidade do lead em `seller_cities` (só vendedor **ativo**). Trocar a cidade de vendedor muda o dono dos leads dela sem migração. |
| Escopo da importação | Todos os estabelecimentos **ativos** com CNAE principal na lista, nas **UFs** que aparecem em `seller_cities`. Cidade nova numa UF já importada mostra leads na hora. **Mudou o escopo** (UF nova ou lista de CNAEs) → a próxima execução do timer reimporta mesmo no mesmo mês. |
| Volume | ~50–60 mil lojas ativas com `4781400` só em SC (inclui MEIs). Lista paginada. |
| Já é cliente | CNPJ do lead igual (normalizado) a algum `customers.document` → não entra na importação **e** é filtrado na listagem (cliente cadastrado à mão some da prospecção na hora). |
| Lead descartado ou convertido | Fica guardado; a importação seguinte não o traz de volta. |
| Lead `new` que sumiu da Receita | Apagado na importação seguinte **só se não tiver contatos**. Com contatos, fica (o vendedor descarta se a loja fechou). Assim o histórico do CRM nunca some por causa da importação. |
| CNPJ | Texto de 14 caracteres **alfanuméricos** (desde jul/2026 há CNPJ com letras). Normalização: tira tudo que não é letra/dígito e põe em maiúsculas. |
| Visibilidade dos contatos | Segue a da entidade: quem vê o lead/cliente vê todo o histórico dele (inclusive contatos de outro usuário). Admin vê tudo. |
| Retornos de hoje | O **último** contato de cada lead/cliente, **registrado pelo próprio usuário**, cuja `next_action_date` ≤ hoje, e cuja entidade ele ainda vê. Lead descartado não entra. Contato novo substitui o lembrete anterior; não existe flag "feito". Vale igual para o admin (os retornos **dele**). |
| IA | Nenhuma nesta entrega. |

## Dados

### `seller_cities` (nova)

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | int PK | |
| `user_id` | FK `users.id` | vendedor dono da cidade |
| `city` | str(100) | nome para exibição |
| `state` | str(2) | UF |
| `city_key` | str(100) | `sales._city_key(city)` (sem acento, minúsculo, espaços normalizados) |

`UniqueConstraint("city_key", "state")`.

### `leads` (nova)

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | int PK | |
| `cnpj` | str(14) unique | normalizado (ver Decisões) |
| `name` | str(160) | nome fantasia; vazio → razão social; ambos vazios → CNPJ formatado |
| `phone` | str(30) null | DDD_1 + TELEFONE_1 |
| `email` | str(160) null | minúsculo |
| `address` | str(250) null | tipo + logradouro, número, complemento, bairro, CEP |
| `city` | str(100) | nome para exibição (ver "Nome da cidade") |
| `state` | str(2) | |
| `city_key` | str(100) | `_city_key(city)` |
| `opened_at` | date null | data de início de atividade |
| `status` | str(10) | `new` · `converted` · `discarded` |
| `discard_reason` | str(30) null | `closed` · `not_target` · `competitor` · `other` |
| `customer_id` | FK `customers.id` null | preenchido ao converter |
| `seen_at` | date | data da última importação que trouxe o CNPJ |

`Index("ix_leads_area", "state", "city_key", "status")`.

Motivos de descarte na tela: "Loja fechou", "Não é o nosso público", "Já compra de concorrente", "Outro".

**Nome da cidade:** a Receita grava em maiúsculas sem acento ("JARAGUA DO SUL"). Na importação, se já existe
cliente com o mesmo `city_key` + UF, usa o nome escrito no cliente ("Jaraguá do Sul"); senão, "Title Case"
com conectivos em minúsculo (`da`, `das`, `de`, `do`, `dos`, `e`) → "Jaragua do Sul". A comparação é sempre
pelo `city_key`.

### `contacts` (nova)

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | int PK | |
| `user_id` | FK `users.id` | quem registrou |
| `lead_id` | FK `leads.id` null | |
| `customer_id` | FK `customers.id` null | |
| `channel` | str(10) | `whatsapp` · `call` · `visit` · `email` |
| `notes` | Text null | |
| `next_action_date` | date null | "retornar em" |
| `created_at` | datetime | `server_default=now()` |

`CheckConstraint` exigindo **exatamente um** entre `lead_id` e `customer_id`. Índices em `lead_id` e
`customer_id`.

O SQLite do projeto não liga `PRAGMA foreign_keys` (`database.py`), então **nenhuma regra depende de
cascade do banco**: toda remoção apaga ou ajusta os dependentes explicitamente no código.

### `app_settings` (colunas novas, via `_ensure_columns` em `main.py` + campos no modelo)

- `lead_cnaes` str(200), padrão `"4781400"` — códigos de 7 dígitos separados por vírgula (a tela aceita com
  máscara; grava só dígitos; código inválido → 422).
- `last_lead_import_month` str(7) null — ex. `"2026-10"`.
- `last_lead_import_scope` str(300) null — UFs e CNAEs da última importação, ex. `"SC,PR|4781400"`.
- `last_lead_import_at` datetime null.

`lead_cnaes` entra em `AppSettingsIn` como **opcional** (ausente = não muda) e em `AppSettingsAdminOut`;
os campos `last_lead_import_*` só em `AppSettingsAdminOut`. `update_settings` ganha a linha que grava
`lead_cnaes`.

### Remoção de cliente

`DELETE /customers/{id}` (hoje só bloqueia se tem pedidos) passa a apagar os contatos do cliente e a limpar
`leads.customer_id` que apontem para ele, na mesma transação.

## Importação (`backend/app/lead_import.py`)

Executável com `python -m app.lead_import` (a partir de `backend/`). Na VM, um **timer systemd diário de
madrugada** (`dimarcy-leads.timer` + `.service`), documentado no README de deploy.

**Fonte (verificada em 16/10/2026):** o antigo índice `arquivos.receitafederal.gov.br/dados/cnpj/...` dá 404.
Os dados estão num compartilhamento público do Nextcloud, acessível por WebDAV:

- Base `https://arquivos.receitafederal.gov.br/public.php/webdav/`, autenticação Basic com usuário = token do
  compartilhamento (`YggdBLfdninEJX9`) e senha vazia.
- Listar meses: `PROPFIND` com `Depth: 1` → pastas `YYYY-MM`.
- Baixar: `GET <base>/<YYYY-MM>/<arquivo>.zip`.
- URL base e token ficam em `config.py` (`receita_webdav_url`, `receita_share_token`), sobrescrevíveis pelo
  `.env` — a Receita já mudou o endereço duas vezes.

**Arquivos e formato:** `Estabelecimentos0..9.zip` (~5,3 GB no total), `Empresas0..9.zip` (~1,4 GB),
`Municipios.zip` (43 KB). Cada zip tem um único arquivo com nome estranho (ler a primeira entrada).
CSV com `;`, latin-1, todos os campos entre aspas, sem cabeçalho, e campos podem conter `;` → usar o
módulo `csv`, nunca `split`.

Colunas usadas de Estabelecimentos (índice 0): 0 CNPJ básico, 1 ordem, 2 DV, 4 nome fantasia,
5 situação (`"02"` = ativa), 10 início de atividade (`YYYYMMDD`), 11 CNAE principal (7 dígitos),
13–18 endereço (tipo, logradouro, número, complemento, bairro, CEP), 19 UF, 20 município (código da Receita,
string com zeros à esquerda), 21 DDD 1, 22 telefone 1, 27 e-mail. Empresas: 0 CNPJ básico, 1 razão social.
Municipios: código; nome.

**Passos:**

1. Calcula o escopo atual: UFs distintas de `seller_cities` + `lead_cnaes`. Sem UF → sai.
2. `PROPFIND` → mês mais recente. Mês igual a `last_lead_import_month` **e** escopo igual a
   `last_lead_import_scope` → sai.
3. Baixa `Municipios.zip` → mapa código → nome.
4. Para cada `Estabelecimentos*.zip`: baixa para arquivo temporário, lê em streaming, guarda só situação
   `02` + CNAE principal na lista + UF no escopo; apaga o zip.
5. Para os CNPJs sem nome fantasia, percorre `Empresas*.zip` buscando a razão social pelo CNPJ básico.
6. Numa **única transação**: insere CNPJs novos (`status=new`), atualiza dados cadastrais e `seen_at` dos
   existentes (sem mexer em `status`), apaga leads `new` sem contatos que não vieram nesta importação,
   ignora CNPJs que já são clientes, grava `last_lead_import_month/scope/at`.

Qualquer erro (rede, zip corrompido, número de colunas ≠ 30) → nenhuma escrita no banco; erro no log do
systemd; o timer do dia seguinte tenta de novo. Duração estimada: 20–40 min.

Download, parser de linha e aplicação no banco ficam em funções separadas, para o teste usar zips pequenos
gerados localmente (sem internet).

## Ranking dos leads

Ordem da lista (critérios em sequência, sem pontuação escondida):

1. Tem telefone ou e-mail (primeiro).
2. Abriu há até 730 dias (primeiro).
3. Mais clientes **ativos** da Di Marcy na mesma cidade (empresa toda, não só do vendedor).
4. `opened_at` mais recente.
5. Nome.

**Clientes ativos por cidade:** uma consulta `MAX(orders.date)` por cliente com `status in SALE_STATUSES`,
juntada a todos os clientes; em Python, `customer_status(last, hoje) == "active"` agrupado por
`(_city_key(city), state)`. Os critérios 1, 2, 4 e 5 vão no `ORDER BY` do SQL; o 3 é aplicado em Python
sobre as linhas filtradas da região (dezenas de milhares no pior caso, admin) antes de paginar.

## API

Todas sob `/api`, mesma autenticação das demais.

| Rota | Quem | O que faz |
|---|---|---|
| `GET /users/{id}/cities` | admin | cidades da região do vendedor |
| `PUT /users/{id}/cities` | admin | substitui a lista; cidade de outro vendedor → 409 com "Corupá já é da região de Fulano." |
| `GET /users/{id}/cities/suggestions` | admin | cidades distintas dos clientes do vendedor, com o nome de quem já tem cada uma (se alguém tem) |
| `GET /users/cities/options` | admin | cidades distintas de clientes e leads (autocompletar) |
| `GET /leads` | todos | vendedor: leads `new` da região dele; admin: todos `new`, com `seller_name` e filtro `seller_id` (`0` = sem vendedor). Filtros `city`, `search`. Ordenado pelo ranking. `limit` (padrão 50) + `offset`; resposta `{items, total}`. CNPJs que já são clientes são excluídos. |
| `GET /leads/{id}` | visibilidade | detalhe |
| `POST /leads/{id}/convert` | visibilidade | ver abaixo |
| `POST /leads/{id}/discard` | visibilidade | `{reason}`; só de `new`; senão 409 |
| `GET /contacts?lead_id=` / `?customer_id=` | visibilidade da entidade | histórico, mais recente primeiro |
| `POST /contacts` | visibilidade da entidade | registra contato |
| `GET /contacts/due` | todos | retornos vencidos (regra na tabela de Decisões), com nome, tipo (lead/cliente), canal e anotação do último contato |
| `GET/PUT /settings` | (existente) | passa a incluir `lead_cnaes` e `last_lead_import_*` (admin) |

Lead fora da região do vendedor → 404 (mesmo padrão de `_visible` em `customers.py`).

**Converter (`POST /leads/{id}/convert`):** recebe `CustomerIn`. A lógica de criação do cliente
(dono, geocodificação em background) sai de `routers/customers.py:create` para um helper compartilhado e é
reusada aqui. Dono: vendedor → ele mesmo (ignora `owner_id`); admin → `owner_id` enviado, ou o vendedor da
região do lead se vier vazio. Na mesma transação: `UPDATE leads SET status='converted', customer_id=… WHERE
id=… AND status='new'` (0 linhas → 409 "Este lead já foi tratado."), e os contatos do lead passam para o
cliente (`customer_id` preenchido, `lead_id` nulo).

**Painel:** `alerts` em `routers/dashboard.py` ganha `follow_ups_due` (contagem da mesma regra de
`/contacts/due`).

## Telas

### Prospecção (`/leads`, menu de vendedor e de admin em `Layout.jsx`, rota em `App.jsx`)

- Lista no padrão das telas de lista: nome, cidade, telefone, "abriu há X meses" com selo **Nova** quando
  ≤ 730 dias; admin vê também a coluna Vendedor. Filtro por cidade, busca por nome; admin filtra por vendedor.
  Botão **Carregar mais** no fim (paginação de 50).
- Clicar abre o **`LeadPanel`** (componente novo, mesmo visual do `CustomerPanel`): CNPJ, endereço, telefone,
  e-mail; botões **WhatsApp**, **Registrar contato**, **Virar cliente**, **Descartar**; histórico de contatos.
- WhatsApp: `whatsappUrl(phone, text)` — `format.js` ganha o parâmetro opcional `text` (`&text=` com
  `encodeURIComponent`). Texto: "Olá, tudo bem? Sou {vendedor} da Di Marcy. Gostaria de apresentar nossa
  coleção para a {loja}. Posso te enviar o catálogo?"
- **Virar cliente** abre o `CustomerFormModal` preenchido; o modal ganha uma prop opcional com a URL de envio
  (padrão `/customers`), usada aqui com `/leads/{id}/convert`.
- **Descartar** pede o motivo.

### Mini-CRM

- Componente **`ContactHistory`** (lista + botão Registrar contato) com fetch próprio por `lead_id` ou
  `customer_id`, usado no `LeadPanel` e no `CustomerPanel` (seção **Contatos**, abaixo de "Últimos pedidos").
- Modal **Registrar contato**: canal, anotação, "retornar em" (data opcional, atalhos +3 / +7 / +30 dias).
- `AlertStrip` do Painel ganha "**N retornos para hoje**" (`follow_ups_due`) → tela **Retornos**
  (`/follow-ups`, rota em `App.jsx`): lista com nome, lead/cliente, último contato e botão Registrar contato.

### Usuários

- Formulário do usuário vendedor ganha **Cidades da região**: lista de cidade/UF com autocompletar
  (`/users/cities/options`), texto livre aceito; erro do 409 mostrado no formulário.
- Botão **Sugerir pelas cidades dos clientes**: preenche com as sugestões; as que já são de outro vendedor
  aparecem marcadas ("já é de Fulano") e não são incluídas automaticamente.

### Configurações

- Campo **CNAEs da prospecção** (lista separada por vírgula) e o texto "Última importação: outubro/2026,
  em 16/10/2026" (ou "Ainda não importado").

## Testes

`backend/test_leads.py`, no padrão dos demais (asserts, SQLite descartável, `python test_leads.py`):

- **Importação** com zips pequenos gerados no teste (inclui campo com `;` entre aspas e CNPJ alfanumérico):
  só ativas + CNAE + UF entram; nome fantasia vazio → razão social; nome da cidade usa a grafia do cliente
  quando existe; CNPJ já cliente (com `document` formatado) fica de fora; `discarded` não volta; `new` sumido
  sem contatos é apagado e com contatos fica; erro no meio não grava nada; mês e escopo iguais não rodam;
  escopo diferente roda no mesmo mês.
- **Região:** mesma cidade com acento/maiúscula diferente em dois vendedores → 409; vendedor só vê leads
  da região; mudar a cidade de vendedor muda o dono; admin vê todos, inclusive "sem vendedor"; vendedor
  inativo → leads como "sem vendedor".
- **Listagem:** paginação (`total` + `offset`); cliente cadastrado à mão com o CNPJ do lead tira o lead da
  lista; ranking na ordem dos critérios.
- **Conversão:** cria cliente com o dono certo (vendedor; admin com e sem `owner_id`); lead vira `converted`;
  contatos passam para o cliente; segunda conversão → 409; vendedor não converte lead de fora da região (404).
- **CRM:** retornos usam só o último contato e só os do próprio usuário; contato novo sem data tira o
  lembrete; lead descartado sai dos retornos; contato precisa de exatamente um entre lead e cliente;
  visibilidade segue a entidade; `follow_ups_due` no Painel bate com `/contacts/due`.
- **Cliente apagado:** contatos somem e `leads.customer_id` é limpo.
- **Configurações:** `lead_cnaes` inválido → 422; ausente não altera.

Verificação manual: rodar a importação real uma vez localmente (SC) e conferir quantidade (~50–60 mil) e
amostra de Jaraguá do Sul antes de ligar o timer na VM.

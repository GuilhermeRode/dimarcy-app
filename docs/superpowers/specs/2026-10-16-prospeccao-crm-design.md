# Prospecção de clientes novos + mini-CRM

**Data:** 2026-10-16

## Objetivo

Ajudar os vendedores a gerar vendas novas:

- **Prospecção:** mostrar ao vendedor lojas de vestuário que ainda não são clientes, dentro da
  região que ele atende, a partir dos dados abertos de CNPJ da Receita Federal.
- **Mini-CRM:** registrar cada contato (com lead ou cliente) e lembrar o vendedor do retorno
  combinado ("Retornos de hoje").

## Fora do escopo

- IA (ranking ou mensagem gerada). Ranking por regras fixas e mensagem de WhatsApp com texto fixo.
- Google Places / APIs pagas de CNPJ. Pode virar etapa futura para enriquecer contatos.
- Botão "importar agora" na tela — a importação é mensal pelo timer (ver "Importação").
- Editar ou apagar contato registrado (histórico só de inclusão). Exportar leads.
- Mudar o dono de clientes existentes por causa da região: a região vale **só para leads**.
- CNAE secundário: filtra só pelo CNAE **principal**.

## Decisões

| Tema | Decisão |
|---|---|
| Fonte dos dados | Dados abertos de CNPJ da Receita Federal (gratuito, mensal). |
| CNAEs | Lista editável pelo admin em Configurações; padrão só `4781400` (comércio varejista de artigos do vestuário e acessórios). |
| Região do vendedor | Lista explícita de cidades (cidade + UF) por vendedor, definida pelo admin. **Uma cidade pertence a no máximo um vendedor** (constraint única no banco). |
| Alcance da região | Só leads. Clientes atuais continuam com o dono atual, mesmo em cidade de outro vendedor. |
| Dono do lead | **Não é gravado**: calculado pela cidade do lead em `seller_cities`. Trocar a cidade de vendedor muda o dono dos leads dela sem migração. |
| Escopo da importação | Todos os estabelecimentos **ativos** com CNAE principal na lista, nas **UFs** que aparecem em `seller_cities`. Cidade nova na região mostra leads na hora, sem reimportar. |
| Já é cliente | CNPJ do lead igual (só dígitos) a algum `customers.document` → não entra / não aparece. |
| Lead descartado ou convertido | Fica guardado; a importação seguinte não o traz de volta. |
| Lead `new` que sumiu da Receita | Apagado na importação seguinte, junto com seus contatos. |
| Visibilidade dos contatos | Segue a da entidade: quem vê o lead/cliente vê todo o histórico dele (inclusive contatos de outro usuário). Admin vê tudo. |
| Retornos de hoje | O **último** contato de cada lead/cliente cuja `next_action_date` ≤ hoje. Contato novo substitui o lembrete anterior; não existe flag "feito". |
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
| `cnpj` | str(14) unique | só dígitos |
| `name` | str(160) | nome fantasia; vazio → razão social |
| `phone` | str(30) null | DDD + telefone 1 da Receita |
| `email` | str(160) null | |
| `address` | str(250) null | tipo + logradouro, número, complemento, bairro, CEP |
| `city` | str(100) | nome do município da Receita, em "Title Case" |
| `state` | str(2) | |
| `city_key` | str(100) index | `_city_key(city)` |
| `opened_at` | date null | data de início de atividade |
| `status` | str(10) index | `new` · `converted` · `discarded` |
| `discard_reason` | str(30) null | `closed` · `not_target` · `competitor` · `other` |
| `customer_id` | FK `customers.id` null | preenchido ao converter |
| `seen_at` | date | data da última importação que trouxe o CNPJ |

Motivos de descarte na tela: "Loja fechou", "Não é o nosso público", "Já compra de concorrente", "Outro".

### `contacts` (nova)

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | int PK | |
| `user_id` | FK `users.id` | quem registrou |
| `lead_id` | FK `leads.id` null, `ondelete=CASCADE` | |
| `customer_id` | FK `customers.id` null | |
| `channel` | str(10) | `whatsapp` · `call` · `visit` · `email` |
| `notes` | Text null | |
| `next_action_date` | date null | "retornar em" |
| `created_at` | datetime | `server_default=now()` |

`CheckConstraint` exigindo **exatamente um** entre `lead_id` e `customer_id`.

### `app_settings` (colunas novas, via `_ensure_columns` em `main.py`)

- `lead_cnaes` str(200), padrão `"4781400"` — códigos separados por vírgula (aceita com ou sem máscara na tela; grava só dígitos).
- `last_lead_import_month` str(7) null — ex. `"2026-10"`.
- `last_lead_import_at` datetime null.

## Importação (`backend/app/lead_import.py`)

Executável com `python -m app.lead_import` (a partir de `backend/`). Na VM, um **timer systemd diário de madrugada**
(`dimarcy-leads.timer` + `.service`), documentado no README de deploy; o script sai na hora se o mês mais
recente já foi importado, então rodar todo dia é barato e serve de "tentar de novo" após falha.

Passos:

1. Descobre a pasta mais recente (`YYYY-MM`) em
   `https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/`. Igual a `last_lead_import_month` → sai.
2. Lê CNAEs de `app_settings.lead_cnaes` e UFs distintas de `seller_cities`. Sem UF → sai (nada a importar).
3. Baixa `Municipios.zip` → mapa código Receita → nome do município.
4. Para cada `Estabelecimentos0..9.zip`: baixa para arquivo temporário, lê o CSV em streaming
   (`;`, latin-1, sem cabeçalho), guarda só linhas com situação cadastral `02` (ativa), CNAE principal na
   lista e UF no conjunto; apaga o zip.
5. Para os CNPJs sem nome fantasia, percorre `Empresas0..9.zip` buscando a razão social pelo CNPJ básico
   (8 primeiros dígitos).
6. Numa **única transação**: insere CNPJs novos (`status=new`), atualiza dados cadastrais e `seen_at` dos
   existentes (sem mexer em `status`), apaga leads `new` que não vieram nesta importação, ignora CNPJs que
   já são clientes, grava `last_lead_import_month/at`.

Qualquer erro (rede, zip corrompido, formato inesperado) → nenhuma escrita no banco; erro vai para o log do
systemd; o timer do dia seguinte tenta de novo. As posições de coluna e nomes de arquivo são conferidos
contra os arquivos reais no plano de implementação, antes do código.

O parser de linha e a aplicação no banco ficam em funções separadas do download, para o teste usar zips
pequenos gerados localmente (sem internet).

## Ranking dos leads

Ordem da lista (sem pontuação escondida, só critérios em sequência):

1. Tem telefone ou e-mail (primeiro).
2. Abriu há até 730 dias (primeiro).
3. Mais clientes **ativos** da Di Marcy na mesma cidade (`customer_status == "active"`, empresa toda).
4. `opened_at` mais recente.
5. Nome.

## API

Todas sob `/api`, mesma autenticação das demais.

| Rota | Quem | O que faz |
|---|---|---|
| `GET /users/{id}/cities` | admin | cidades da região do vendedor |
| `PUT /users/{id}/cities` | admin | substitui a lista; cidade de outro vendedor → 409 com "Corupá já é da região de Fulano." |
| `GET /users/cities/suggestions` | admin | por vendedor, cidades dos clientes dele, marcando as que conflitam com outro vendedor; mais a lista de cidades distintas dos leads (para o autocompletar) |
| `GET /leads` | todos | vendedor: leads `new` da região dele; admin: todos `new`, com `seller_name` e filtro `seller_id` (inclui "sem vendedor"). Filtros `city`, `search`. Ordenado pelo ranking. |
| `GET /leads/{id}` | todos (visibilidade) | detalhe + contatos |
| `POST /leads/{id}/convert` | todos (visibilidade) | recebe `CustomerIn`; cria o cliente (dono = vendedor da região; admin pode escolher), marca `converted`, move os contatos do lead para o cliente (`customer_id` preenchido, `lead_id` nulo) — tudo numa transação |
| `POST /leads/{id}/discard` | todos (visibilidade) | `{reason}` → `discarded` |
| `GET /contacts?lead_id=` / `?customer_id=` | visibilidade da entidade | histórico, mais recente primeiro |
| `POST /contacts` | visibilidade da entidade | registra contato |
| `GET /contacts/due` | todos | retornos vencidos (≤ hoje) visíveis ao usuário, com nome, tipo (lead/cliente), canal e anotação do último contato |
| `GET/PUT /settings` | (existente) | passa a incluir `lead_cnaes` (admin) e `last_lead_import_month/at` |

Lead fora da região do vendedor → 404 (mesmo padrão de `_visible` em `customers.py`).
Vendedor inativo: suas cidades continuam reservadas; para a listagem, cidade de vendedor inativo conta
como "sem vendedor" (só o admin vê esses leads).

## Telas

### Prospecção (`/leads`, menu, todos)

- Lista no padrão das telas de lista: nome, cidade, telefone, "abriu há X meses" com selo **Nova** quando
  ≤ 730 dias; admin vê também a coluna Vendedor. Filtro por cidade, busca por nome; admin filtra por vendedor.
- Clicar abre painel lateral no padrão do `CustomerPanel`: CNPJ, endereço, telefone, e-mail; botões
  **WhatsApp** (link `whatsappUrl` com texto fixo), **Registrar contato**, **Virar cliente**, **Descartar**;
  histórico de contatos.
- Texto do WhatsApp: "Olá, tudo bem? Sou {vendedor} da Di Marcy. Gostaria de apresentar nossa coleção
  para a {loja}. Posso te enviar o catálogo?"
- **Virar cliente** abre o `CustomerFormModal` preenchido com os dados do lead.
- **Descartar** pede o motivo.

### Mini-CRM

- Modal **Registrar contato**: canal, anotação, "retornar em" (data opcional, atalhos +3 / +7 / +30 dias).
- `CustomerPanel` ganha a seção **Contatos** (abaixo de "Últimos pedidos") com o histórico e o botão
  Registrar contato.
- `AlertStrip` do Painel ganha "**N retornos para hoje**" → `/contacts/due` na tela **Retornos**
  (`/follow-ups`): lista com nome, lead/cliente, último contato e botão Registrar contato.

### Usuários

- Formulário do usuário vendedor ganha **Cidades da região**: lista de cidade/UF com autocompletar a partir
  das cidades de clientes e leads; erro inline quando a cidade é de outro vendedor.
- Botão **Sugerir pelas cidades dos clientes**: preenche com as cidades dos clientes do vendedor,
  destacando as que já são de outro vendedor (o admin decide).

### Configurações

- Campo **CNAEs da prospecção** (lista separada por vírgula) e o texto "Última importação: outubro/2026,
  em 16/10/2026".

## Testes

`backend/test_leads.py`, no padrão dos demais (asserts, SQLite descartável, `python test_leads.py`):

- **Importação** com zips pequenos gerados no teste: só ativas + CNAE + UF entram; nome fantasia vazio →
  razão social; CNPJ já cliente (com `document` formatado) fica de fora; `discarded` não volta; `new`
  sumido é apagado; erro no meio não grava nada; mês já importado não roda.
- **Região:** mesma cidade com acento/maiúscula diferente em dois vendedores → 409; vendedor só vê leads
  da região; mudar a cidade de vendedor muda o dono; admin vê todos, inclusive "sem vendedor"; vendedor
  inativo → leads como "sem vendedor".
- **Conversão:** cria cliente com o dono certo, lead vira `converted`, contatos passam para o cliente;
  vendedor não converte lead de fora da região (404).
- **CRM:** retornos usam só o último contato; contato novo sem data tira o lembrete; contato precisa de
  exatamente um entre lead e cliente; visibilidade segue a entidade.
- **Ranking:** ordem dos critérios.

Verificação manual: rodar a importação real uma vez localmente (SC) e conferir quantidade e amostra de
Jaraguá do Sul antes de ligar o timer na VM.

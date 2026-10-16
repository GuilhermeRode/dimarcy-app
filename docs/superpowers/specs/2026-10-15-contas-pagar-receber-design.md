# Contas a pagar e a receber

**Data:** 2026-10-15 (revisado após revisão da spec contra o código)

## Objetivo

Controlar dentro do app o dinheiro que entra e sai, no lugar da planilha de contas a pagar:

- **A receber:** parcelas geradas automaticamente dos pedidos entregues, com baixa manual
  (conferida com o que o banco/contabilidade informa).
- **A pagar:** despesas da empresa lançadas à mão, com repetição mensal.

Só o administrador acessa. Vendedores não veem nada disso.

## Fora do escopo

- Gerar boleto e emitir NF-e — continuam no sistema atual da empresa. Pode virar outra etapa,
  usando as parcelas daqui como base.
- Importar extrato / arquivo de retorno do banco — a baixa é manual.
- Fluxo de caixa com gráfico, aviso de vencidas no Painel, exportar para Excel, anexar comprovantes.
- Categorias editáveis pela tela (começam como lista fixa no código).
- Paginação das listas (o volume da empresa é pequeno; filtro padrão "Em aberto").
- Gerar parcelas em massa para pedidos entregues antes desta funcionalidade (ver "Pedidos antigos").

## Decisões

| Tema | Decisão |
|---|---|
| Armazenamento | Uma tabela `financial_entries` para os dois lados, com `kind` = `receivable` / `payable`. |
| Quando nasce o a receber | Quando o pedido **entra** em Entregue, por qualquer caminho (troca de status, edição, criação já entregue). |
| Data-base dos prazos | O dia em que o pedido foi marcado como entregue (`clock.today_br()`). |
| Quanto gerar | **Saldo** = total do pedido − soma do `amount` das parcelas já **pagas** daquele pedido. Saldo ≤ 0 → não gera nada. |
| Duplicidade | Só gera se o pedido **não tem parcelas em aberto**. |
| Pedido sai de Entregue | Para **qualquer** outro status (cancelado, enviado, orçamento, clique errado): parcelas **em aberto** do pedido são removidas; as pagas ficam. Voltar para Entregue gera de novo o saldo. Ajustes manuais feitos nas parcelas abertas se perdem nesse vai-e-volta (aceito). |
| Pedido editado continuando Entregue | Parcelas não mudam sozinhas; o admin ajusta à mão. |
| Valor das parcelas | Saldo dividido em **centavos inteiros**; a diferença vai para a 1ª parcela. |
| Situação | Calculada, não gravada: **Paga** (`paid_at` preenchido), **Vencida** (aberta e `due_date` < hoje), **Em aberto**. |
| Cliente do a receber | Não é gravado: vem sempre de `order_id → orders.customer_id` (nunca fica desatualizado). |
| Repetição (a pagar) | "Repetir mensalmente por N meses" (1–60) cria N lançamentos independentes. |
| Onde fica na tela | Abas dentro de Faturamento: Vendas (atual) · Contas a receber · Contas a pagar. |

### Prazo do pedido → parcelas (dias após a entrega)

`installment_days(payment_terms) -> list[int]`:

1. `"Quinzenal"` → `[15, 30, 45, …, 150]` (10 parcelas).
2. Texto que se divide por `/` em números inteiros → esses números (`"30/60/90"` → `[30, 60, 90]`;
   também cobre prazos futuros como `"28/56"`).
3. Qualquer outro texto (inclui `"À vista"`) → `[0]` (1 parcela, vence no dia da entrega).

## Dados

Nova tabela `financial_entries` (criada pelo `create_all`; nenhuma coluna nova em tabelas existentes):

| Coluna | Tipo | Uso |
|---|---|---|
| `id` | int PK | |
| `kind` | `String(10)`, indexado | `receivable` / `payable` |
| `description` | `String(200)` | "Pedido 00123 — parcela 2/3", "Aluguel (3/12)" |
| `amount` | `Numeric(12,2)` | valor previsto (> 0) |
| `due_date` | `Date`, indexado | vencimento |
| `paid_at` | `Date` nulo | data da baixa; nulo = em aberto |
| `paid_amount` | `Numeric(12,2)` nulo | valor efetivamente pago (juros/desconto) |
| `payment_method` | `String(40)` nulo | no a receber, copiado do pedido |
| `notes` | `Text` nulo | |
| `order_id` | FK `orders.id` nulo, indexado | a receber de pedido |
| `supplier` | `String(160)` nulo | a pagar, texto livre |
| `category` | `String(40)` nulo | a pagar, uma de `PAYABLE_CATEGORIES` |
| `installment`, `installments` | int nulos | "2 de 3" (parcelas de pedido e repetições mensais) |
| `created_at` | `DateTime` | |

`PAYABLE_CATEGORIES = ["Matéria-prima", "Aluguel", "Salários", "Impostos", "Energia", "Manutenção", "Outros"]`
(valores em português por serem conteúdo do negócio).

Dinheiro: cálculos em centavos inteiros / `Decimal`, nunca somando `float` (o `Order.total` é float →
converter com `round(total * 100)`). Totais do resumo arredondados a 2 casas.

## Backend

Novo `app/finance.py` com a lógica (sem FastAPI), e `app/routers/finance.py` com as rotas.
O `APIRouter` de finanças inteiro leva `dependencies=[Depends(require_admin)]`.
Datas de "hoje" sempre por `clock.today_br()` chamado **pelo módulo** (`from . import clock`),
para os testes poderem trocar o relógio, e passadas ao banco como parâmetro — nunca
`func.current_date()` (o Postgres de produção roda em UTC).

**Lógica (`app/finance.py`):**
- `installment_days(terms)` — regra acima.
- `split_cents(total_cents, n) -> list[int]` — resto na 1ª parcela.
- `create_order_installments(db, order, today)` — se o pedido tem parcela em aberto, não faz nada;
  senão calcula o saldo e, se > 0, cria um `receivable` por parcela. Não faz commit.
- `remove_open_installments(db, order)` — remove as em aberto do pedido. Não faz commit.
- `add_months(d, n)` — mantém o dia, limitado ao fim do mês. A repetição usa
  `add_months(primeiro_vencimento, i)` para i = 0…N−1 (não encadeia: 31/01 → 28/02 → **31/03**).

**Ganchos nos pedidos (`routers/orders.py`)** — em `create`, `update` e `change_status`:
1. Guardar o status antigo **antes** de atribuir os campos novos.
2. Atribuir os campos (itens, desconto, prazo, status).
3. `db.flush()` (o pedido novo precisa de `id` para a descrição "Pedido 00123").
4. Se entrou em Entregue → `create_order_installments`; se saiu de Entregue → `remove_open_installments`.
5. Um único `db.commit()` — pedido e parcelas salvam juntos. E-mails continuam depois do commit.

**Outras mudanças em pedidos:**
- `DELETE /orders/{id}`: se o pedido tem qualquer lançamento financeiro → 400
  "Este pedido tem parcelas lançadas. Exclua as parcelas antes." (Senão, no Postgres a FK daria erro 500
  e no SQLite ficariam parcelas órfãs.)
- `POST /orders` por vendedor: só aceita status `quote` ou `confirmed` (hoje a API aceitaria
  `delivered`, o que geraria contas a receber por um vendedor).
- `full()` / `GET /orders/{id}` **não** incluem parcelas (vendedores também leem essa rota).

**Rotas (`/api/finance`):**

| Método e caminho | O que faz |
|---|---|
| `GET /entries?kind=&status=open\|overdue\|paid\|all&start=&end=&search=&category=&order_id=` | lista com nome do cliente (via pedido); período filtra por vencimento; `search` com `ilike` em descrição, nome do cliente e fornecedor |
| `GET /summary?kind=` | cartões (ver abaixo) |
| `POST /entries` | lança manualmente: `kind`, campos, `order_id` opcional (só para `receivable`), `repeat_months` opcional (padrão 1) |
| `PUT /entries/{id}` | edita descrição, valor, vencimento, forma, observações, fornecedor, categoria. Lançamento **pago** não pode mudar `amount` → 400 (desfazer a baixa antes) |
| `POST /entries/{id}/pay` | baixa: `paid_at` (padrão hoje), `paid_amount` (> 0, padrão o valor), `payment_method`. Já paga → 400 |
| `POST /entries/{id}/unpay` | limpa `paid_at` e `paid_amount`; mantém `payment_method` |
| `POST /entries/{id}/split` | `amount` x (0 < x < valor) e `due_date`. A original **mantém** o vencimento e passa a valer `valor − x`; uma nova é criada com `x`, o `due_date` informado, os demais campos copiados e " (restante)" no fim da descrição. Só lançamento em aberto |
| `DELETE /entries/{id}` | exclui |
| `POST /orders/{order_id}/generate` | o mesmo `create_order_installments` com hoje como data-base; 400 se o pedido não está Entregue ou se já tem parcela em aberto ou se o saldo é 0 |

**Resumo (`/summary`)** — por `kind`, só lançamentos abertos usam `amount`, pagos usam `paid_amount`:
- **Vencido:** abertos com `due_date` < hoje (soma e quantidade).
- **Vence em 7 dias:** abertos com hoje ≤ `due_date` ≤ hoje + 7.
- **Em aberto:** todos os abertos (inclui vencidos).
- **Recebido/Pago no mês:** soma de `paid_amount` com `paid_at` no mês corrente.

Validações: `amount` > 0 e finito; `category` na lista (para `payable`); `kind` só os dois valores;
`repeat_months` entre 1 e 60; `order_id`, se enviado, precisa existir. Mensagens de erro em português.

### Pedidos antigos e saldo pendente

Pedidos entregues antes desta funcionalidade não ganham parcelas automaticamente (a maioria já
foi paga). No detalhe do pedido Entregue **sem parcela em aberto e com saldo > 0** aparece o botão
**"Gerar parcelas"** (data-base hoje). O mesmo botão cobre o pedido que foi pago em parte, cancelado
e entregue de novo. O botão fica desabilitado enquanto a requisição roda; o servidor revalida.

## Frontend

- **Faturamento** ganha abas no topo: `Vendas` (`/revenue`, tela atual), `Contas a receber`
  (`/revenue/receivables`), `Contas a pagar` (`/revenue/payables`). Rotas admin-only como hoje.
- **Uma página `Finance.jsx`** atende as duas abas, recebendo `kind`. Diferenças por `kind`:
  colunas (Cliente/Pedido × Fornecedor/Categoria), filtro de categoria só no a pagar, rótulo
  "Recebido no mês" × "Pago no mês".
- **"Lançar conta"** nas duas abas. No a receber, campo opcional "Nº do pedido"; no a pagar,
  fornecedor e categoria.
- **Cartões de resumo** (Vencido · Vence em 7 dias · Em aberto · Recebido/Pago no mês); clicar
  aplica o filtro correspondente.
- **Filtros:** situação (padrão Em aberto), período de vencimento, busca.
- **Tabela:** Vencimento · Cliente/Fornecedor · Pedido/Categoria · Parcela · Valor · Situação ·
  botão "Dar baixa" (ou data de pagamento, se paga). Vencidas destacadas.
- **Modal de baixa:** data (hoje), valor recebido/pago (o da parcela), forma de pagamento.
- **Modal de edição** (clicar na linha): campos editáveis (valor travado se paga) + Desmembrar,
  Desfazer baixa, Excluir (com confirmação via `useConfirm`, como nas outras telas).
- **Modal "Lançar conta":** descrição, valor, 1º vencimento, forma, observações,
  "Repetir mensalmente por [N] meses", e os campos específicos do lado.
- **Detalhe do pedido** (só admin): bloco "Parcelas" que chama `/api/finance/entries?order_id=`,
  com situação e "Dar baixa"; botão "Gerar parcelas" conforme a regra acima.

## Testes

`backend/test_finance.py`, no estilo dos `test_*.py` atuais (asserts simples, SQLite temporário,
`TestClient`, rodado com `python test_finance.py`; relógio trocado com `clock.today_br = lambda: TODAY`):

- `installment_days`: cada prazo do formulário, Quinzenal = 10, "28/56", texto desconhecido = `[0]`.
- `split_cents`: 10000 ÷ 3 = 3334 / 3333 / 3333; soma sempre igual ao total.
- Pedido marcado entregue gera parcelas com valores e vencimentos certos; marcar de novo não duplica.
- Pedido criado já como entregue (admin) gera parcelas; vendedor não consegue criar como entregue.
- Pedido com total 0 (desconto de 100%) não gera parcela.
- Sair de Entregue (cancelado e outro status) remove as abertas e mantém as pagas; voltar a
  Entregue gera só o saldo.
- Excluir pedido com parcelas → 400.
- Baixa (e baixa em já paga → 400), desfazer baixa, editar valor de paga → 400,
  desmembrar (soma preservada; original mantém vencimento; não desmembra paga).
- Repetição mensal: 12 lançamentos a partir de 31/01 → 28/02 (ou 29/02), 31/03.
- "Gerar parcelas": funciona em pedido entregue antigo; 400 quando não está entregue ou já tem abertas.
- Filtros de situação e resumo (inclui "pago no mês" usando `paid_amount`).
- Vendedor recebe 403 em todas as rotas `/api/finance`; `GET /orders/{id}` não traz parcelas.

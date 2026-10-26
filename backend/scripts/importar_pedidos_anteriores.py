"""Cadastra o histórico de compras de antes do app (aba "Pedidos 2026" do Plano de Ação) nos clientes.

Cada linha do CSV (data;cliente;cidade;valor[;cliente_id]) vira uma compra anterior do cliente: só data e valor,
sem produtos. Aparece no painel do cliente ("Compras anteriores"); não entra no Painel, no Faturamento
nem na situação ativo/inativo do cliente.

O cliente é achado pelo nome (sem diferenciar maiúsculas/acentos); se houver mais de um com o mesmo
nome, desempata pela cidade. Uma coluna cliente_id preenchida (conferida à mão) vale no lugar do nome. Se alguma linha não achar exatamente 1 cliente, lista todas e para sem
gravar nada.

Roda direto no servidor, sem deploy e sem dependências (só Python 3).
Sem --apply só simula. Com --apply, faz antes uma cópia do banco (<banco>.bak-AAAAMMDD-HHMMSS).
Pode rodar mais de uma vez: cada rodada substitui todo o histórico anterior (não duplica).

Uso (na pasta do backend, onde fica o dimarcy.db):
    python3 importar_pedidos_anteriores.py pedidos_2026.csv              # simula
    python3 importar_pedidos_anteriores.py pedidos_2026.csv --apply      # grava
    python3 importar_pedidos_anteriores.py pedidos_2026.csv --db /caminho/dimarcy.db --apply
"""
import csv
import os
import sqlite3
import sys
import time
import unicodedata
from collections import defaultdict

# Same columns as models.PastOrder; created here too so the script works before the deploy.
CREATE = """CREATE TABLE IF NOT EXISTS past_orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers (id),
    date DATE NOT NULL,
    amount NUMERIC(10, 2) NOT NULL)"""


def fold(text):
    """Lowercase without accents and extra spaces, so "Vivi&ana  Modas" == "vivi&ana modas"."""
    text = "".join(c for c in unicodedata.normalize("NFD", text or "").casefold() if unicodedata.category(c) != "Mn")
    return " ".join(text.split())


def match(rows, customers):
    """rows: (date, name, city, amount); customers: (id, name, city). Returns ([(customer_id, date, amount)], problems)."""
    by_name = defaultdict(list)
    for cid, name, city in customers:
        by_name[fold(name)].append((cid, fold(city)))
    ids = {cid for cid, _, _ in customers}
    found, problems = [], []
    for n, (day, name, city, amount, given_id) in enumerate(rows, start=2):  # line 1 is the header
        if given_id:  # reviewed by hand: trust the id, as long as the customer exists
            if given_id in ids:
                found.append((given_id, day, amount))
            else:
                problems.append("linha %d: %s — cliente_id %d não existe" % (n, name, given_id))
            continue
        same_name = by_name.get(fold(name), [])
        cands = [c for c in same_name if c[1] == fold(city)] if len(same_name) > 1 else same_name
        if len(cands) == 1:
            found.append((cands[0][0], day, amount))
        else:
            why = ("cliente não encontrado" if not same_name else
                   "%d clientes com esse nome, %s nessa cidade" % (len(same_name), "vários" if cands else "nenhum"))
            problems.append("linha %d: %s (%s) — %s" % (n, name, city, why))
    return found, problems


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [(r["data"], r["cliente"], r["cidade"], round(float(r["valor"]), 2), int(r.get("cliente_id") or 0))
                for r in csv.DictReader(f, delimiter=";")]


def main(argv):
    db_path = argv[argv.index("--db") + 1] if "--db" in argv else "dimarcy.db"
    apply = "--apply" in argv
    args = [a for a in argv if not a.startswith("--") and a != db_path]
    if len(args) != 1 or not os.path.isfile(args[0]):
        raise SystemExit("Informe o CSV: python3 importar_pedidos_anteriores.py pedidos_2026.csv [--apply]")
    if not os.path.isfile(db_path):
        raise SystemExit("Banco não encontrado: %s (use --db /caminho/do/dimarcy.db)" % os.path.abspath(db_path))

    rows = read_csv(args[0])
    con = sqlite3.connect(db_path)
    try:
        found, problems = match(rows, con.execute("SELECT id, name, city FROM customers").fetchall())
        print("Banco: %s" % os.path.abspath(db_path))
        print("  linhas no CSV: %d · clientes achados: %d linhas · total: R$ %.2f"
              % (len(rows), len(found), sum(a for _, _, a in found)))
        if problems:
            print("  %d linha(s) sem cliente certo — nada foi gravado:" % len(problems))
            for p in problems:
                print("    " + p)
            raise SystemExit(1)
        if not apply:
            print("Simulação: nada foi gravado. Rode de novo com --apply para gravar.")
            return
        backup = "%s.bak-%s" % (db_path, time.strftime("%Y%m%d-%H%M%S"))
        with sqlite3.connect(backup) as dst:  # safety copy, using SQLite's own online backup
            con.backup(dst)
        print("Cópia de segurança: %s" % backup)
        with con:  # one transaction: all or nothing
            con.execute(CREATE)
            con.execute("CREATE INDEX IF NOT EXISTS ix_past_orders_customer_id ON past_orders (customer_id)")
            con.execute("DELETE FROM past_orders")
            con.executemany("INSERT INTO past_orders (customer_id, date, amount) VALUES (?, ?, ?)", found)
        print("Gravado: %d compras anteriores." % len(found))
    finally:
        con.close()


if __name__ == "__main__":
    main(sys.argv[1:])

"""Apaga pedidos de teste e faz um pedido que fica passar a ser o nº 00001.

- Sem argumentos: só lista os pedidos (número, data, cliente, vendedor, itens, parcelas).
- --keep N: apaga TODOS os outros pedidos (com itens e parcelas do Faturamento) e renumera o pedido N para 1,
  inclusive as parcelas dele ("Pedido 00003 — parcela 1/2" vira "Pedido 00001 — parcela 1/2").
  O próximo pedido criado será o 00002.
- Sem --apply só simula. Com --apply, faz antes uma cópia do banco (<banco>.bak-AAAAMMDD-HHMMSS).

Uso (na pasta do backend, onde fica o dimarcy.db):
    python3 renumerar_pedidos.py                     # lista os pedidos
    python3 renumerar_pedidos.py --keep 3            # simula
    python3 renumerar_pedidos.py --keep 3 --apply    # grava
"""
import os
import sqlite3
import sys
import time


def list_orders(cur):
    rows = cur.execute("""
        SELECT o.id, o.date, c.name, u.name, o.status,
               (SELECT COUNT(*) FROM order_items i WHERE i.order_id = o.id),
               (SELECT COALESCE(SUM(i.quantity * i.unit_price), 0) FROM order_items i WHERE i.order_id = o.id) - o.discount,
               (SELECT COUNT(*) FROM financial_entries f WHERE f.order_id = o.id)
        FROM orders o JOIN customers c ON c.id = o.customer_id JOIN users u ON u.id = o.seller_id
        ORDER BY o.id""").fetchall()
    for oid, d, customer, seller, status, items, total, entries in rows:
        print("  Pedido %05d · %s · %s · vendedor %s · %s · %d itens · R$ %.2f · %d parcelas"
              % (oid, d, customer, seller, status, items, total, entries))
    return [r[0] for r in rows]


def renumber(cur, keep):
    others = [oid for (oid,) in cur.execute("SELECT id FROM orders WHERE id != ?", (keep,))]
    for oid in others:
        cur.execute("DELETE FROM financial_entries WHERE order_id = ?", (oid,))
        cur.execute("DELETE FROM order_items WHERE order_id = ?", (oid,))
        cur.execute("DELETE FROM orders WHERE id = ?", (oid,))
    if keep != 1:
        cur.execute("UPDATE orders SET id = 1 WHERE id = ?", (keep,))
        cur.execute("UPDATE order_items SET order_id = 1 WHERE order_id = ?", (keep,))
        cur.execute("UPDATE financial_entries SET order_id = 1, description = replace(description, ?, ?) WHERE order_id = ?",
                    ("Pedido %05d" % keep, "Pedido 00001", keep))
    return others


def main(argv):
    db_path = argv[argv.index("--db") + 1] if "--db" in argv else "dimarcy.db"
    keep = int(argv[argv.index("--keep") + 1]) if "--keep" in argv else None
    apply = "--apply" in argv
    if not os.path.isfile(db_path):
        raise SystemExit("Banco não encontrado: %s (use --db /caminho/do/dimarcy.db)" % os.path.abspath(db_path))

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    print("Banco: %s\nPedidos hoje:" % os.path.abspath(db_path))
    ids = list_orders(cur)
    if keep is None:
        con.close()
        return print("Rode com --keep <número do pedido que fica> para simular.")
    if keep not in ids:
        con.close()
        raise SystemExit("Pedido %05d não existe. Nada foi feito." % keep)

    if apply:  # safety copy, using SQLite's own online backup
        backup = "%s.bak-%s" % (db_path, time.strftime("%Y%m%d-%H%M%S"))
        with sqlite3.connect(backup) as dst:
            con.backup(dst)
        print("Cópia de segurança: %s" % backup)

    removed = renumber(cur, keep)
    print("Apagados: %s" % (", ".join("%05d" % i for i in removed) or "nenhum"))
    print("Pedido %05d agora é o 00001. Depois:" % keep)
    list_orders(cur)
    if apply:
        con.commit()
        print("Gravado.")
    else:
        con.rollback()
        print("Simulação: nada foi gravado. Rode de novo com --apply para gravar.")
    con.close()


if __name__ == "__main__":
    main(sys.argv[1:])

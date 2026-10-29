"""Volta para "Primeiro contato" os leads liberados (aba Liberados) em que o vendedor ainda não fez nada:
nenhum contato registrado por um vendedor. Os que o vendedor já trabalhou continuam liberados.
Leads que o próprio vendedor cadastrou à mão (nunca foram liberados) não são tocados.
Limpa released_at, então a cota semanal de liberação volta a contar do zero para eles.

Roda direto no servidor, sem deploy e sem dependências (só Python 3).
Sem --apply só simula. Com --apply, faz antes uma cópia do banco (<banco>.bak-AAAAMMDD-HHMMSS).
Pode rodar mais de uma vez. Só depois do deploy da versão com "Primeiro contato" (o script confere).

Uso (na pasta do backend, onde fica o dimarcy.db):
    python3 scripts/voltar_liberados.py              # simula
    python3 scripts/voltar_liberados.py --apply      # grava
    python3 scripts/voltar_liberados.py --db /caminho/dimarcy.db --apply
"""
import os
import sqlite3
import sys
import time

UNTOUCHED = """
    FROM leads l
    WHERE l.status = 'new'
      AND NOT (l.edited = 1 AND l.released_at IS NULL)  -- typed in by the seller: theirs from the start
      AND NOT EXISTS (SELECT 1 FROM contacts c JOIN users u ON u.id = c.user_id
                      WHERE c.lead_id = l.id AND u.role != 'admin')
"""


def run(con, apply):
    cur = con.cursor()
    # leads.edited comes with the app version that has "Primeiro contato" (PR #41): an older app would hide these leads
    if "edited" not in {r[1] for r in cur.execute("PRAGMA table_info(leads)")}:
        raise SystemExit("O app no servidor ainda não tem a etapa Primeiro contato: faça o deploy antes. Nada foi gravado.")
    # per seller, for the report: the active seller whose region has the lead's city (leads.city_owners)
    by_seller = cur.execute("""
        SELECT COALESCE((SELECT u.name FROM seller_cities sc JOIN users u ON u.id = sc.user_id
                         WHERE sc.city_key = l.city_key AND sc.state = l.state AND u.active = 1), '(sem vendedor)'),
               COUNT(*)""" + UNTOUCHED + " GROUP BY 1 ORDER BY 2 DESC").fetchall()
    kept = cur.execute("SELECT COUNT(*) FROM leads WHERE status = 'new'").fetchone()[0] - sum(n for _, n in by_seller)
    cur.execute("UPDATE leads SET status = 'contacted', released_at = NULL WHERE id IN (SELECT l.id" + UNTOUCHED + ")")
    if apply:
        con.commit()
    else:
        con.rollback()
    return by_seller, kept


def main(argv):
    db_path = argv[argv.index("--db") + 1] if "--db" in argv else "dimarcy.db"
    apply = "--apply" in argv
    if not os.path.isfile(db_path):
        raise SystemExit("Banco não encontrado: %s (use --db /caminho/do/dimarcy.db)" % os.path.abspath(db_path))

    if apply:  # safety copy, using SQLite's own online backup
        backup = "%s.bak-%s" % (db_path, time.strftime("%Y%m%d-%H%M%S"))
        with sqlite3.connect(db_path) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
        print("Cópia de segurança: %s" % backup)

    con = sqlite3.connect(db_path)
    try:
        by_seller, kept = run(con, apply)
    finally:
        con.close()
    print("Banco: %s" % os.path.abspath(db_path))
    print("Voltam para Primeiro contato: %d" % sum(n for _, n in by_seller))
    for name, n in by_seller:
        print("  %s: %d" % (name, n))
    print("Continuam liberados (vendedor já registrou contato ou cadastrou o lead): %d" % kept)
    print("Gravado." if apply else "Simulação: nada foi gravado. Rode de novo com --apply para gravar.")


if __name__ == "__main__":
    main(sys.argv[1:])

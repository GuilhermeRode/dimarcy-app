"""Libera os leads em "Primeiro contato" cuja cidade está na região de UM só vendedor ativo: vão para ele,
como o botão Liberar sem "Liberar para" (routers/leads.py: release). Cidades de vários vendedores ou de
nenhum continuam em Primeiro contato (o admin escolhe pela tela).
Conta na cota semanal (released_at = agora).

Roda direto no servidor, sem deploy e sem dependências (só Python 3).
Sem --apply só simula. Com --apply, faz antes uma cópia do banco (<banco>.bak-AAAAMMDD-HHMMSS).

Uso (na pasta do backend, onde fica o dimarcy.db):
    python3 scripts/liberar_primeiro_contato.py              # simula
    python3 scripts/liberar_primeiro_contato.py --apply      # grava
    python3 scripts/liberar_primeiro_contato.py --db /caminho/dimarcy.db --apply
"""
import os
import sqlite3
import sys
import time

# the active sellers (or admins with a region, leads.REGION_ROLES) of each city — leads.city_owners
OWNERS = """
    SELECT sc.city_key, sc.state, MIN(u.id) AS user_id, MIN(u.name) AS name, COUNT(DISTINCT u.id) AS n
    FROM seller_cities sc JOIN users u ON u.id = sc.user_id
    WHERE u.active = 1 AND u.role IN ('seller', 'admin')
    GROUP BY sc.city_key, sc.state
"""


def run(con, apply):
    cur = con.cursor()
    rows = cur.execute("""
        SELECT l.id, o.user_id, o.name, o.n FROM leads l
        LEFT JOIN (""" + OWNERS + """) o ON o.city_key = l.city_key AND o.state = l.state
        WHERE l.status = 'contacted'""").fetchall()
    one = [(lid, uid, name) for lid, uid, name, n in rows if n == 1]
    several = sum(1 for r in rows if (r[3] or 0) > 1)
    nobody = sum(1 for r in rows if not r[3])
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())  # naive UTC, like lead_import.utcnow
    cur.executemany("UPDATE leads SET status = 'new', released_at = ?, seller_id = ? WHERE id = ? AND status = 'contacted'",
                    [(now, uid, lid) for lid, uid, _ in one])
    if apply:
        con.commit()
    else:
        con.rollback()
    by_seller = {}
    for _, _, name in one:
        by_seller[name] = by_seller.get(name, 0) + 1
    return by_seller, several, nobody


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
        by_seller, several, nobody = run(con, apply)
    finally:
        con.close()
    print("Banco: %s" % os.path.abspath(db_path))
    print("Liberados: %d" % sum(by_seller.values()))
    for name, n in sorted(by_seller.items(), key=lambda kv: -kv[1]):
        print("  %s: %d" % (name, n))
    print("Continuam em Primeiro contato — cidade com mais de um vendedor: %d · sem vendedor: %d" % (several, nobody))
    print("Gravado." if apply else "Simulação: nada foi gravado. Rode de novo com --apply para gravar.")


if __name__ == "__main__":
    main(sys.argv[1:])

"""Vincula uma cor já cadastrada (padrão: "Sortidas") a TODOS os produtos que ainda não a têm.

Não cria a cor nem mexe nas outras cores dos produtos: só acrescenta a que falta.
Sem --apply só simula. Com --apply, faz antes uma cópia do banco (<banco>.bak-AAAAMMDD-HHMMSS).

Uso (na pasta do backend, onde fica o dimarcy.db):
    python3 vincular_cor.py                      # simula com a cor "Sortidas"
    python3 vincular_cor.py --apply              # grava
    python3 vincular_cor.py --cor "Outra cor"    # outro nome de cor
"""
import os
import sqlite3
import sys
import time


def main(argv):
    db_path = argv[argv.index("--db") + 1] if "--db" in argv else "dimarcy.db"
    color_name = argv[argv.index("--cor") + 1] if "--cor" in argv else "Sortidas"
    apply = "--apply" in argv
    if not os.path.isfile(db_path):
        raise SystemExit("Banco não encontrado: %s (use --db /caminho/do/dimarcy.db)" % os.path.abspath(db_path))

    con = sqlite3.connect(db_path)
    print("Banco: %s" % os.path.abspath(db_path))
    found = con.execute("SELECT id, name FROM colors WHERE lower(trim(name)) = lower(trim(?))", (color_name,)).fetchall()
    if len(found) != 1:
        similar = [n for (n,) in con.execute("SELECT name FROM colors WHERE lower(name) LIKE ? ORDER BY name",
                                             ("%" + color_name.strip()[:4].lower() + "%",))]
        con.close()
        raise SystemExit('Cor "%s" não encontrada. Parecidas: %s. Use --cor "<nome exato>". Nada foi feito.'
                         % (color_name, ", ".join(similar) or "nenhuma"))
    color_id, real_name = found[0]

    missing = con.execute("""
        SELECT p.id, p.reference, p.description FROM products p
        WHERE NOT EXISTS (SELECT 1 FROM product_color pc WHERE pc.product_id = p.id AND pc.color_id = ?)
        ORDER BY p.reference""", (color_id,)).fetchall()
    total = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    print('Cor "%s" (id %d): falta em %d de %d produtos.' % (real_name, color_id, len(missing), total))
    for _, ref, desc in missing:
        print("  %s · %s" % (ref, desc))
    if not missing or not apply:
        con.close()
        return print("Nada a fazer." if not missing else "Simulação: nada foi gravado. Rode de novo com --apply para gravar.")

    backup = "%s.bak-%s" % (db_path, time.strftime("%Y%m%d-%H%M%S"))
    with sqlite3.connect(backup) as dst:  # safety copy, using SQLite's own online backup
        con.backup(dst)
    print("Cópia de segurança: %s" % backup)
    with con:  # one transaction: all or nothing
        con.executemany("INSERT INTO product_color (product_id, color_id) VALUES (?, ?)",
                        [(pid, color_id) for pid, _, _ in missing])
    con.close()
    print("Gravado: %d produtos agora têm a cor %s." % (len(missing), real_name))


if __name__ == "__main__":
    main(sys.argv[1:])
